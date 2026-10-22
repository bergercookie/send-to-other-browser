#!/usr/bin/env python3
"""Regenerate the screenshots embedded in README.md.

Starts headless Chromium with the extension loaded and the real native host wired
to fake target browsers (they only record the launch), then captures the popup in
the three states the docs show:

    popup-default.png   tabs selected, target browsers discovered
    popup-sent.png      after "Send to Vivaldi"
    popup-error.png     no native host registered

Requires Playwright's Chromium build (``uv run playwright install chromium``).
Run it through `just screenshots`.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path

from PIL import Image
from playwright.sync_api import BrowserContext
from playwright.sync_api import Page
from playwright.sync_api import Playwright
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
from install import CHROMIUM_DEBUG_EXTENSION_ID  # noqa: E402
from install import HOST_NAME  # noqa: E402

POPUP_URL = f"chrome-extension://{CHROMIUM_DEBUG_EXTENSION_ID}/popup/popup.html"

# Body width the popup gets in a real popup panel (popup.css min-width). Opened
# in a tab instead, the body would stretch across the whole window, so the width
# is pinned to this before shooting.
POPUP_WIDTH = 260
WINDOW_SIZE = (900, 800)
FAKE_BROWSERS = ("vivaldi", "google-chrome", "chromium", "brave-browser", "microsoft-edge")
TAB_COUNT = 3
WAIT = 20_000


STYLE_JS = """
const width = arguments[0];
document.documentElement.style.background = "#fff";
let style = document.getElementById("screenshot-style");
if (!style) {
  style = document.createElement("style");
  style.id = "screenshot-style";
  document.head.append(style);
}
style.textContent =
  "body { background: #fff; margin: 0 !important; padding: 12px !important;" +
  ` width: ${width}px; box-sizing: content-box; }`;
"""


class _Page(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = f"<title>{self.path}</title><h1>{self.path}</h1>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


def make_home(base: Path) -> tuple[Path, dict[str, str | float | bool]]:
    """Throwaway $HOME with fake browser executables and the host registered."""
    home = base / "home"
    bin_dir = home / "bin"
    bin_dir.mkdir(parents=True)
    for name in FAKE_BROWSERS:
        exe = bin_dir / name
        exe.write_text("#!/bin/sh\nexit 0\n")
        exe.chmod(0o755)
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "host" / "install.py"),
            "--browser",
            "chromium",
            # The screenshots use the unpacked development build.
            "--debug",
            "--dest",
            str(home / ".config/chromium/NativeMessagingHosts"),
        ],
        check=True,
        capture_output=True,
    )
    env: dict[str, str | float | bool] = dict(os.environ)
    env["HOME"] = str(home)
    env["SEND_TO_OTHER_BROWSER_PATH"] = str(bin_dir)
    return home, env


def start_chromium(
    playwright: Playwright, workspace: Path, env: dict[str, str | float | bool]
) -> BrowserContext:
    extension = ROOT / "extension-chromium"
    return playwright.chromium.launch_persistent_context(
        workspace / "profile",
        channel="chromium",
        headless=True,
        viewport={"width": WINDOW_SIZE[0], "height": WINDOW_SIZE[1]},
        device_scale_factor=2,
        env=env,
        args=[
            f"--disable-extensions-except={extension}",
            f"--load-extension={extension}",
        ],
    )


def open_popup(context: BrowserContext, base: str) -> Page:
    """Open TAB_COUNT web tabs, then the popup with exactly those pre-selected."""
    for i in range(TAB_COUNT):
        page = context.new_page()
        page.goto(f"{base}/tab-{i + 1}")
    # A first popup visit (in a tab) is the only place the extension's tab ids
    # are visible; the second one gets them via ?tabIds=, like the e2e tests.
    page = context.new_page()
    page.goto(POPUP_URL)
    tabs = page.evaluate("() => chrome.tabs.query({currentWindow: true})")
    ids = [t["id"] for t in tabs if t["url"].startswith(("http://", "https://"))]
    popup = context.new_page()
    popup.goto(f"{POPUP_URL}?tabIds={','.join(map(str, ids))}")
    return popup


def capture(page: Page, dest: Path) -> None:
    """Screenshot the popup body at its natural popup width."""
    page.evaluate(STYLE_JS.replace("arguments[0]", str(POPUP_WIDTH)))
    page.locator("body").screenshot(path=dest)
    if not dest.is_file() or dest.stat().st_size == 0:
        raise RuntimeError(f"failed to write {dest}")
    # Chrome Web Store screenshots must be 24-bit PNGs without an alpha channel.
    with Image.open(dest) as screenshot:
        screenshot.convert("RGB").save(dest)


def wait_status(page: Page, contains: str) -> None:
    page.locator("#status").filter(has_text=contains).wait_for(timeout=WAIT)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=ROOT / "docs" / "screenshots",
        help="directory for the PNGs (default: docs/screenshots)",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    workspace = Path(tempfile.mkdtemp(prefix="screenshots-"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        home, env = make_home(workspace)
        base = f"http://127.0.0.1:{server.server_port}"

        with sync_playwright() as playwright:
            context = start_chromium(playwright, workspace / "success", env)
            try:
                popup = open_popup(context, base)
                popup.locator("#browsers button").first.wait_for(timeout=WAIT)
                capture(popup, args.output / "popup-default.png")
                popup.locator("button[data-browser=vivaldi]").click()
                wait_status(popup, "Sent")
                capture(popup, args.output / "popup-sent.png")
            finally:
                context.close()

            # Same HOME, host unregistered: the popup reports the missing native host.
            manifest = home / ".config" / "chromium" / "NativeMessagingHosts" / f"{HOST_NAME}.json"
            manifest.unlink()
            context = start_chromium(playwright, workspace / "error", env)
            try:
                popup = open_popup(context, base)
                wait_status(popup, "native host")
                capture(popup, args.output / "popup-error.png")
            finally:
                context.close()
    finally:
        server.shutdown()
        server.server_close()
        shutil.rmtree(workspace, ignore_errors=True)

    for png in sorted(args.output.glob("*.png")):
        try:
            shown = png.relative_to(ROOT)
        except ValueError:
            shown = png
        print(f"wrote {shown} ({png.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
