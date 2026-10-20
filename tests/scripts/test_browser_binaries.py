from pathlib import Path

import pytest

from scripts.browser_binaries import firefox_binary


def test_firefox_binary_unwraps_launcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    native = tmp_path / "firefox-unwrapped/lib/firefox/firefox"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"\x7fELF native Firefox placeholder")
    native.chmod(0o755)
    launcher = tmp_path / "bin/firefox"
    launcher.parent.mkdir()
    launcher.write_text(f'#!/bin/sh\nexec -a "$0" "{native}" "$@"\n')
    launcher.chmod(0o755)
    monkeypatch.setenv("FIREFOX_BIN", str(launcher))

    assert firefox_binary() == str(native)


def test_firefox_binary_rejects_launcher_without_native_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = tmp_path / "firefox"
    launcher.write_text('#!/bin/sh\nexec /missing/firefox "$@"\n')
    launcher.chmod(0o755)
    monkeypatch.setenv("FIREFOX_BIN", str(launcher))

    assert firefox_binary() is None
