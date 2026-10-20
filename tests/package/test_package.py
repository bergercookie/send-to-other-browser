import json
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def copy_package_sources(destination: Path) -> None:
    for directory in ("extension", "extension-chromium", "host"):
        shutil.copytree(ROOT / directory, destination / directory)
    shutil.copy2(ROOT / "justfile", destination / "justfile")


def archive_names(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as archive:
        return {name.removeprefix("./") for name in archive.namelist()}


def test_just_package_builds_all_artifacts(tmp_path: Path) -> None:
    copy_package_sources(tmp_path)
    version = json.loads((tmp_path / "extension" / "manifest.json").read_text())["version"]

    subprocess.run(["just", "package"], cwd=tmp_path, check=True)

    firefox = tmp_path / "dist" / f"send-to-other-browser-extension-{version}.zip"
    web_store = tmp_path / "dist" / f"send-to-other-browser-chrome-web-store-{version}.zip"
    native_host = tmp_path / "dist" / f"send-to-other-browser-host-{version}.tar.gz"
    assert {path.name for path in (firefox, web_store, native_host) if path.is_file()} == {
        firefox.name,
        web_store.name,
        native_host.name,
    }
    assert {"manifest.json", "background.js"} <= archive_names(firefox)
    assert {"manifest.json", "background.js"} <= archive_names(web_store)
    with zipfile.ZipFile(web_store) as archive:
        assert "key" not in json.loads(archive.read("manifest.json"))
    with tarfile.open(native_host) as archive:
        assert {"host/install.py", "host/send_to_other_browser.py"} <= set(archive.getnames())
