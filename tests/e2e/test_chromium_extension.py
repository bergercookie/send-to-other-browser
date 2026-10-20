"""End-to-end: Chromium-family extension sends through the native host to Firefox."""

import glob
import os
import shutil
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
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[2]
EXTENSION_ID = "loagchgjndmjgeopkhjlamacnkbenajk"
POPUP_URL = f"chrome-extension://{EXTENSION_ID}/popup/popup.html"


def find_browser() -> str | None:
    configured = [os.environ.get(name) for name in ("CHROME_BIN", "VIVALDI_BIN", "CHROMIUM_BIN")]
    on_path = [shutil.which(name) for name in ("google-chrome", "vivaldi", "chromium")]
    bundled = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome")
    return next((path for path in [*configured, *on_path, *bundled] if path), None)


BROWSER = find_browser()
DRIVER = os.environ.get("CHROMEDRIVER") or shutil.which("chromedriver")
pytestmark = pytest.mark.skipif(
    not BROWSER or not DRIVER, reason="needs Chrome/Vivaldi and chromedriver"
)

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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[str, Path]]:
    home, bin_dir, log_dir = tmp_path / "home", tmp_path / "bin", tmp_path / "logs"
    for directory in (home, bin_dir, log_dir):
        directory.mkdir()
    executable = bin_dir / "firefox"
    executable.write_text(FAKE_BROWSER)
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    destinations = {
        "chrome": ".config/google-chrome/NativeMessagingHosts",
        "chromium": ".config/chromium/NativeMessagingHosts",
        "vivaldi": ".config/vivaldi/NativeMessagingHosts",
    }
    for browser, destination in destinations.items():
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "host" / "install.py"),
                "--browser",
                browser,
                "--dest",
                str(home / destination),
            ],
            check=True,
            capture_output=True,
            env={**os.environ, "PYTHONPATH": str(ROOT / "host")},
        )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SEND_TO_OTHER_BROWSER_PATH", str(bin_dir))
    monkeypatch.setenv("E2E_LOG_DIR", str(log_dir))
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", log_dir
    server.shutdown()


@pytest.fixture
def chromium(chromium_environment: tuple[str, Path]) -> Iterator[webdriver.Chrome]:
    assert BROWSER is not None
    assert DRIVER is not None
    options = Options()
    options.binary_location = BROWSER
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument(f"--disable-extensions-except={ROOT / 'extension-chromium'}")
    options.add_argument(f"--load-extension={ROOT / 'extension-chromium'}")
    driver = webdriver.Chrome(options=options, service=Service(executable_path=DRIVER))
    yield driver
    driver.quit()


def wait_for_log(path: Path) -> list[str]:
    deadline = time.time() + 10
    while time.time() < deadline:
        if path.exists() and path.read_text().strip():
            return path.read_text().splitlines()
        time.sleep(0.1)
    raise AssertionError("Firefox was never started")


def test_chromium_extension_sends_selected_tabs_to_firefox(
    chromium: webdriver.Chrome, chromium_environment: tuple[str, Path]
) -> None:
    base_url, log_dir = chromium_environment
    urls = [f"{base_url}/one", f"{base_url}/two"]
    for url in urls:
        chromium.switch_to.new_window("tab")
        chromium.get(url)
    chromium.get(POPUP_URL)
    tabs = chromium.execute_async_script(
        "const done = arguments[arguments.length - 1]; chrome.tabs.query({}).then(done);"
    )
    tab_ids = [tab["id"] for tab in tabs if tab.get("url") in urls]
    chromium.get(f"{POPUP_URL}?tabIds={','.join(map(str, tab_ids))}")
    button = WebDriverWait(chromium, 10).until(
        lambda driver: driver.find_element(By.CSS_SELECTOR, "button[data-browser=firefox]")
    )
    button.click()
    WebDriverWait(chromium, 10).until(
        lambda driver: "Sent 2 tabs" in driver.find_element(By.ID, "status").text
    )
    assert wait_for_log(log_dir / "firefox.log") == urls
