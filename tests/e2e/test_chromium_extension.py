"""End-to-end: Chromium-family extension sends through the native host to Firefox."""

import os
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import BrowserContext
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
EXTENSION_ID = "loagchgjndmjgeopkhjlamacnkbenajk"
POPUP_URL = f"chrome-extension://{EXTENSION_ID}/popup/popup.html"

FAKE_BROWSER = """#!/bin/sh
printf '%s\\n' "$@" >> "$E2E_LOG_DIR/firefox.log"
"""


class _Page(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = f"<title>{self.path}</title>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        pass


@pytest.fixture
def chromium_environment(
    tmp_path: Path,
) -> Iterator[tuple[str, Path, dict[str, str | float | bool]]]:
    home, bin_dir, log_dir = tmp_path / "home", tmp_path / "bin", tmp_path / "logs"
    for directory in (home, bin_dir, log_dir):
        directory.mkdir()
    executable = bin_dir / "firefox"
    executable.write_text(FAKE_BROWSER)
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    # Chromium reads user-level hosts from <user-data-dir>/NativeMessagingHosts, so with
    # a custom profile the $HOME/.config locations are never consulted.
    destinations = [
        ("chrome", home / ".config/google-chrome/NativeMessagingHosts"),
        ("chromium", home / ".config/chromium/NativeMessagingHosts"),
        ("vivaldi", home / ".config/vivaldi/NativeMessagingHosts"),
        ("chromium", tmp_path / "profile" / "NativeMessagingHosts"),
    ]
    for browser, destination in destinations:
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "host" / "install.py"),
                "--browser",
                browser,
                "--dest",
                str(destination),
            ],
            check=True,
            capture_output=True,
            env={**os.environ, "PYTHONPATH": str(ROOT / "host")},
        )
    browser_env: dict[str, str | float | bool] = {
        **os.environ,
        "HOME": str(home),
        "SEND_TO_OTHER_BROWSER_PATH": str(bin_dir),
        "E2E_LOG_DIR": str(log_dir),
    }
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", log_dir, browser_env
    server.shutdown()


@pytest.fixture
def chromium(
    chromium_environment: tuple[str, Path, dict[str, str | float | bool]], tmp_path: Path
) -> Iterator[BrowserContext]:
    extension = ROOT / "extension-chromium"
    _, _, browser_env = chromium_environment
    with sync_playwright() as playwright:
        if not Path(playwright.chromium.executable_path).is_file():
            pytest.skip("needs Playwright Chromium (run: uv run playwright install chromium)")
        context = playwright.chromium.launch_persistent_context(
            tmp_path / "profile",
            channel="chromium",
            headless=True,
            env=browser_env,
            args=[
                f"--disable-extensions-except={extension}",
                f"--load-extension={extension}",
            ],
        )
        context.set_default_timeout(10_000)
        context.set_default_navigation_timeout(10_000)
        yield context
        context.close()


def wait_for_log(path: Path) -> list[str]:
    deadline = time.time() + 10
    while time.time() < deadline:
        if path.exists() and path.read_text().strip():
            return path.read_text().splitlines()
        time.sleep(0.1)
    raise AssertionError("Firefox was never started")


def test_chromium_extension_sends_selected_tabs_to_firefox(
    chromium: BrowserContext,
    chromium_environment: tuple[str, Path, dict[str, str | float | bool]],
) -> None:
    base_url, log_dir, _ = chromium_environment
    urls = [f"{base_url}/one", f"{base_url}/two"]
    for url in urls:
        page = chromium.new_page()
        page.goto(url)
    extension_page = chromium.new_page()
    extension_page.goto(POPUP_URL)
    tabs = extension_page.evaluate("() => chrome.tabs.query({})")
    tab_ids = [tab["id"] for tab in tabs if tab.get("url") in urls]
    popup = chromium.new_page()
    popup.goto(f"{POPUP_URL}?tabIds={','.join(map(str, tab_ids))}")
    button = popup.locator("button[data-browser=firefox]")
    button.wait_for()
    button.click()
    popup.locator("#status").filter(has_text="Sent 2 tabs").wait_for()
    assert wait_for_log(log_dir / "firefox.log") == urls
