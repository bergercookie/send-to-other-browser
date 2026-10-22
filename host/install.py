#!/usr/bin/env python3
"""Register (or remove) the native messaging manifest for supported browsers.

install.py                 # install for Firefox, Chrome, Chromium, and Vivaldi
install.py --uninstall
install.py --browser chrome
install.py --debug         # allow the unpacked development build of the Chromium extension
install.py --browser firefox --dest DIR  # custom directory (used by tests)
"""

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

HOST_NAME = "send_to_other_browser"
FIREFOX_EXTENSION_ID = "send-to-other-browser@bergercookie"
# The Chrome Web Store item: the extension installed from the store runs under this id.
CHROMIUM_EXTENSION_ID = "aidoknmhcobkkpkgldckffccnnoadifo"
# The unpacked development build (extension-chromium/manifest.json "key"); --debug registers it.
CHROMIUM_DEBUG_EXTENSION_ID = "loagchgjndmjgeopkhjlamacnkbenajk"
# Kept as an alias for clients/tests written before Chromium support.
EXTENSION_ID = FIREFOX_EXTENSION_ID
HERE = Path(__file__).resolve().parent

BROWSER_DESTINATIONS = {
    "firefox": Path(".mozilla/native-messaging-hosts"),
    "zen": Path(".zen/native-messaging-hosts"),
    "librewolf": Path(".librewolf/native-messaging-hosts"),
    "chrome": Path(".config/google-chrome/NativeMessagingHosts"),
    "chromium": Path(".config/chromium/NativeMessagingHosts"),
    "vivaldi": Path(".config/vivaldi/NativeMessagingHosts"),
}
GECKO_BROWSERS = {"firefox", "zen", "librewolf"}


SNAP_NOTE = """\
Snap Firefox detected. It reaches the host through xdg-desktop-portal, which needs
Ubuntu's patched portal (22.04+ / 24.04) and about:config
widget.use-xdg-desktop-portal.native-messaging = 1 (or 2). See README.md#snap-firefox."""


def default_dest(browser: str) -> Path:
    return Path.home() / BROWSER_DESTINATIONS[browser]


def build_manifest(
    host_path: Path, browser: str = "firefox", debug: bool = False
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "name": HOST_NAME,
        "description": "Opens URLs from the Send to Other Browser extension in Firefox, Vivaldi, Chrome, ...",
        "path": str(host_path),
        "type": "stdio",
    }
    if browser in GECKO_BROWSERS:
        manifest["allowed_extensions"] = [FIREFOX_EXTENSION_ID]
    else:
        extension_id = CHROMIUM_DEBUG_EXTENSION_ID if debug else CHROMIUM_EXTENSION_ID
        manifest["allowed_origins"] = [f"chrome-extension://{extension_id}/"]
    return manifest


def install_manifest(
    dest: Path, host: Path, browser: str, uninstall: bool, debug: bool = False
) -> None:
    target = dest / f"{HOST_NAME}.json"
    if uninstall:
        target.unlink(missing_ok=True)
        print(f"removed {target}")
        return
    dest.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_manifest(host, browser, debug), indent=2) + "\n")
    print(f"installed {target} -> {host}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dest", type=Path)
    parser.add_argument(
        "--browser",
        choices=[*BROWSER_DESTINATIONS, "all"],
        help="default: all (Firefox for --dest)",
    )
    parser.add_argument("--host", type=Path, default=HERE / "send_to_other_browser.py")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="allow the unpacked development build of the Chromium extension "
        "(its own extension id) instead of the Chrome Web Store one",
    )
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args(argv)

    browser = args.browser or ("firefox" if args.dest else "all")
    if args.dest and browser == "all":
        parser.error("--dest requires one specific --browser")

    host = args.host.resolve()
    if not args.uninstall and not host.is_file():
        print(f"host script not found: {host}", file=sys.stderr)
        return 1
    if not args.uninstall:
        os.chmod(host, host.stat().st_mode | 0o111)
    browsers = list(BROWSER_DESTINATIONS) if browser == "all" else [browser]
    for current in browsers:
        install_manifest(
            args.dest or default_dest(current), host, current, args.uninstall, args.debug
        )
    if Path("/snap/bin/firefox").exists():
        print(SNAP_NOTE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
