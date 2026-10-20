import json
from pathlib import Path

from scripts import screenshots


def test_make_home_registers_chromium_host(tmp_path: Path) -> None:
    home, env = screenshots.make_home(tmp_path)

    manifest = json.loads(
        (home / ".config/chromium/NativeMessagingHosts/send_to_other_browser.json").read_text()
    )
    assert manifest["allowed_origins"] == [
        f"chrome-extension://{screenshots.CHROMIUM_EXTENSION_ID}/"
    ]
    assert env["HOME"] == str(home)
    assert env["SEND_TO_OTHER_BROWSER_PATH"] == str(home / "bin")
