import io
import json
import os
import stat
import struct
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import install
import pytest
import send_to_other_browser as host

ROOT = Path(__file__).resolve().parents[2]


def make_exe(directory: str, name: str) -> str:
    path = Path(directory) / name
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def test_finds_installed_browsers_only() -> None:
    with tempfile.TemporaryDirectory() as d:
        vivaldi = make_exe(d, "vivaldi-stable")
        chrome = make_exe(d, "google-chrome")
        found = host.discover_browsers(path=d)
    assert found == [
        {"id": "vivaldi", "name": "Vivaldi", "path": vivaldi},
        {"id": "chrome", "name": "Google Chrome", "path": chrome},
    ]


def test_finds_firefox_as_a_destination() -> None:
    with tempfile.TemporaryDirectory() as directory:
        firefox = make_exe(directory, "firefox-esr")
        assert host.discover_browsers(path=directory) == [
            {"id": "firefox", "name": "Mozilla Firefox", "path": firefox}
        ]


@pytest.mark.parametrize("executable", ["firefox", "firefox-esr", "org.mozilla.firefox"])
def test_finds_firefox_install_variants(executable: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = make_exe(directory, executable)
        assert host.discover_browsers(path=directory)[0]["path"] == path


@pytest.mark.parametrize(
    ("browser_id", "name", "executable"),
    [
        ("zen", "Zen Browser", "zen-browser"),
        ("zen", "Zen Browser", "app.zen_browser.zen"),
        ("librewolf", "LibreWolf", "librewolf"),
        ("librewolf", "LibreWolf", "io.gitlab.librewolf-community"),
    ],
)
def test_finds_firefox_forks(browser_id: str, name: str, executable: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = make_exe(directory, executable)
        assert host.discover_browsers(path=directory) == [
            {"id": browser_id, "name": name, "path": path}
        ]


def test_first_install_location_wins() -> None:
    with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
        make_exe(first, "firefox")
        preferred = make_exe(second, "firefox")
        found = host.discover_browsers(path=os.pathsep.join((second, first)))
        assert found[0]["path"] == preferred


def test_finds_snap_vivaldi() -> None:
    with tempfile.TemporaryDirectory() as d:
        exe = make_exe(d, "vivaldi.vivaldi-stable")
        assert host.discover_browsers(path=d) == [{"id": "vivaldi", "name": "Vivaldi", "path": exe}]


def test_nothing_found() -> None:
    with tempfile.TemporaryDirectory() as d:
        assert host.discover_browsers(path=d) == []


def test_extra_path_env_comes_first() -> None:
    env = {"SEND_TO_OTHER_BROWSER_PATH": "/a:/b", "PATH": "/usr/bin"}
    assert host.search_path(env).startswith("/a:/b:/usr/bin:")


def test_minimal_environment_still_searches_standard_locations() -> None:
    # What a host started by xdg-desktop-portal (snap Firefox) sees: no real PATH.
    path = host.search_path({"PATH": "/nonexistent"}).split(os.pathsep)
    for expected in (
        "/usr/bin",
        "/snap/bin",
        "/opt/vivaldi",
        "/opt/google/chrome",
        os.path.expanduser("~/.local/bin"),
    ):
        assert expected in path


def test_searches_snap_flatpak_and_user_install_locations() -> None:
    path = host.search_path({"HOME": "/home/tester", "PATH": "/custom/bin"}).split(os.pathsep)
    for expected in (
        "/snap/bin",
        "/opt/firefox",
        "/var/lib/flatpak/exports/bin",
        "/home/tester/.local/opt/firefox",
        "/home/tester/.local/share/flatpak/exports/bin",
    ):
        assert expected in path


def test_snap_note_links_to_readme_section() -> None:
    assert "README.md#snap-firefox" in install.SNAP_NOTE


def test_accepts_urls_with_different_schemes() -> None:
    for url in (
        "https://example.com/a?b=c#d",
        "http://localhost:8080/",
        "file:///etc/passwd",
        "about:config",
        "moz-extension://id/page.html",
        "mailto:user@example.com",
        "javascript:alert(1)",
    ):
        assert host.is_sendable_url(url)


def test_rejects_non_urls_and_command_switches() -> None:
    for bad in (
        "--user-data-dir=/tmp/x",
        "-https://example.com",
        "https://",
        "relative/path",
        "",
        None,
        42,
    ):
        assert not host.is_sendable_url(bad), repr(bad)


@pytest.fixture
def spawned() -> list[list[str]]:
    return []


@pytest.fixture
def browsers() -> list[dict[str, str]]:
    return [{"id": "vivaldi", "name": "Vivaldi", "path": "/opt/vivaldi"}]


@pytest.fixture
def handle(
    browsers: list[dict[str, str]],
    spawned: list[list[str]],
) -> Callable[[object], dict[str, Any]]:
    def _handle(request: object) -> dict[str, Any]:
        return host.handle_request(request, discover=lambda: browsers, spawn=spawned.append)

    return _handle


def test_ping(handle: Callable[[object], dict[str, Any]]) -> None:
    assert handle({"action": "ping"}) == {"ok": True, "version": host.VERSION}


def test_list(
    handle: Callable[[object], dict[str, Any]],
    browsers: list[dict[str, str]],
) -> None:
    assert handle({"action": "list"}) == {"ok": True, "browsers": browsers}


def test_send_spawns_browser_with_all_urls(
    handle: Callable[[object], dict[str, Any]],
    spawned: list[list[str]],
) -> None:
    reply = handle(
        {
            "action": "send",
            "browser": "vivaldi",
            "urls": ["https://a.example/", "http://b.example/x"],
        }
    )
    assert spawned == [["/opt/vivaldi", "https://a.example/", "http://b.example/x"]]
    assert reply == {"ok": True, "opened": 2, "skipped": [], "browser": "vivaldi"}


def test_send_to_firefox() -> None:
    spawned: list[list[str]] = []
    firefox = {"id": "firefox", "name": "Mozilla Firefox", "path": "/usr/bin/firefox"}
    reply = host.handle_request(
        {"action": "send", "browser": "firefox", "urls": ["https://example.com/"]},
        discover=lambda: [firefox],
        spawn=spawned.append,
    )
    assert reply["ok"]
    assert spawned == [["/usr/bin/firefox", "https://example.com/"]]


def test_send_never_forces_a_new_window(
    handle: Callable[[object], dict[str, Any]],
    spawned: list[list[str]],
) -> None:
    # Without extra switches a running browser opens the URLs as tabs in its existing window.
    handle({"action": "send", "browser": "vivaldi", "urls": ["https://a.example/"]})
    argv = spawned[0]
    assert argv[0] == "/opt/vivaldi"
    assert not [a for a in argv[1:] if a.startswith("-")]


def test_send_keeps_non_http_urls_but_drops_command_switches(
    handle: Callable[[object], dict[str, Any]],
    spawned: list[list[str]],
) -> None:
    reply = handle(
        {
            "action": "send",
            "browser": "vivaldi",
            "urls": ["https://a.example/", "file:///etc/passwd", "--evil"],
        }
    )
    assert spawned == [["/opt/vivaldi", "https://a.example/", "file:///etc/passwd"]]
    assert reply["skipped"] == ["--evil"]


def test_send_with_only_invalid_urls_fails_without_spawning(
    handle: Callable[[object], dict[str, Any]],
    spawned: list[list[str]],
) -> None:
    reply = handle({"action": "send", "browser": "vivaldi", "urls": ["not a URL"]})
    assert not reply["ok"]
    assert spawned == []


def test_send_to_missing_browser(
    handle: Callable[[object], dict[str, Any]],
    spawned: list[list[str]],
) -> None:
    reply = handle({"action": "send", "browser": "chrome", "urls": ["https://a.example/"]})
    assert not reply["ok"]
    assert "not found" in reply["error"]
    assert spawned == []


def test_send_cannot_run_arbitrary_executables(
    handle: Callable[[object], dict[str, Any]],
    spawned: list[list[str]],
) -> None:
    reply = handle({"action": "send", "browser": "/bin/sh", "urls": ["https://a.example/"]})
    assert not reply["ok"]
    assert spawned == []


def test_send_validates_url_list(
    handle: Callable[[object], dict[str, Any]],
    spawned: list[list[str]],
) -> None:
    cases: tuple[object, ...] = (None, [], "https://a.example/")
    for urls in cases:
        assert not handle({"action": "send", "browser": "vivaldi", "urls": urls})["ok"]
    too_many = ["https://a.example/"] * (host.MAX_URLS + 1)
    assert not handle({"action": "send", "browser": "vivaldi", "urls": too_many})["ok"]
    assert spawned == []


def test_spawn_failure_is_reported(browsers: list[dict[str, str]]) -> None:
    def boom(argv: list[str]) -> None:
        raise OSError("exec format error")

    reply = host.handle_request(
        {"action": "send", "browser": "vivaldi", "urls": ["https://a.example/"]},
        discover=lambda: browsers,
        spawn=boom,
    )
    assert not reply["ok"]
    assert "exec format error" in reply["error"]


def test_unknown_action_and_garbage(handle: Callable[[object], dict[str, Any]]) -> None:
    assert not handle({"action": "rm -rf"})["ok"]
    assert not handle([1, 2])["ok"]


def frame(obj: object) -> bytes:
    body = json.dumps(obj).encode()
    return struct.pack("=I", len(body)) + body


def unframe_all(data: bytes) -> list[Any]:
    out: list[Any] = []
    stream = io.BytesIO(data)
    while (msg := host.read_message(stream)) is not None:
        out.append(msg)
    return out


def test_roundtrip() -> None:
    buf = io.BytesIO()
    host.write_message(buf, {"ok": True, "n": "é"})
    assert unframe_all(buf.getvalue()) == [{"ok": True, "n": "é"}]


def test_serve_answers_each_request_until_eof() -> None:
    stdin = io.BytesIO(frame({"action": "ping"}) + frame({"action": "nope"}))
    stdout = io.BytesIO()
    assert host.serve(stdin, stdout) == 0
    replies = unframe_all(stdout.getvalue())
    assert [r["ok"] for r in replies] == [True, False]


def test_serve_rejects_oversized_message() -> None:
    stdin = io.BytesIO(struct.pack("=I", host.MAX_MESSAGE_BYTES + 1))
    stdout = io.BytesIO()
    assert host.serve(stdin, stdout) == 1
    assert not unframe_all(stdout.getvalue())[0]["ok"]


def test_serve_rejects_invalid_json() -> None:
    body = b"not json"
    stdin = io.BytesIO(struct.pack("=I", len(body)) + body)
    stdout = io.BytesIO()
    assert host.serve(stdin, stdout) == 1
    assert not unframe_all(stdout.getvalue())[0]["ok"]


def test_install_and_uninstall() -> None:
    with tempfile.TemporaryDirectory() as d:
        dest = Path(d) / "nmh"
        assert install.main(["--dest", str(dest)]) == 0
        manifest = json.loads((dest / "send_to_other_browser.json").read_text())
        assert manifest["name"] == "send_to_other_browser"
        assert manifest["type"] == "stdio"
        assert manifest["allowed_extensions"] == [install.EXTENSION_ID]
        assert os.path.isabs(manifest["path"])
        assert os.access(manifest["path"], os.X_OK)
        assert install.main(["--dest", str(dest), "--uninstall"]) == 0
        assert not (dest / "send_to_other_browser.json").exists()


@pytest.mark.parametrize("browser", ["chrome", "chromium", "vivaldi"])
def test_install_chromium_native_manifest(browser: str) -> None:
    with tempfile.TemporaryDirectory() as d:
        dest = Path(d) / "nmh"
        assert install.main(["--browser", browser, "--dest", str(dest)]) == 0
        manifest = json.loads((dest / "send_to_other_browser.json").read_text())
        assert manifest["allowed_origins"] == [
            f"chrome-extension://{install.CHROMIUM_EXTENSION_ID}/"
        ]
        assert "allowed_extensions" not in manifest


@pytest.mark.parametrize("browser", ["chrome", "chromium", "vivaldi"])
def test_install_chromium_native_manifest_debug(browser: str) -> None:
    with tempfile.TemporaryDirectory() as d:
        dest = Path(d) / "nmh"
        assert install.main(["--browser", browser, "--debug", "--dest", str(dest)]) == 0
        manifest = json.loads((dest / "send_to_other_browser.json").read_text())
        assert manifest["allowed_origins"] == [
            f"chrome-extension://{install.CHROMIUM_DEBUG_EXTENSION_ID}/"
        ]
        assert "allowed_extensions" not in manifest


@pytest.mark.parametrize("browser", ["firefox", "zen", "librewolf"])
def test_install_gecko_native_manifest(browser: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        dest = Path(directory) / "nmh"
        assert install.main(["--browser", browser, "--dest", str(dest)]) == 0
        manifest = json.loads((dest / "send_to_other_browser.json").read_text())
        assert manifest["allowed_extensions"] == [install.FIREFOX_EXTENSION_ID]
        assert "allowed_origins" not in manifest


def test_debug_flag_leaves_the_gecko_manifest_alone() -> None:
    with tempfile.TemporaryDirectory() as directory:
        dest = Path(directory) / "nmh"
        assert install.main(["--browser", "firefox", "--debug", "--dest", str(dest)]) == 0
        manifest = json.loads((dest / "send_to_other_browser.json").read_text())
        assert manifest["allowed_extensions"] == [install.FIREFOX_EXTENSION_ID]
        assert "allowed_origins" not in manifest


def test_default_destinations_cover_supported_browser_families(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert install.main([]) == 0
    for browser, relative in install.BROWSER_DESTINATIONS.items():
        manifest = json.loads((tmp_path / relative / f"{install.HOST_NAME}.json").read_text())
        key = "allowed_extensions" if browser in install.GECKO_BROWSERS else "allowed_origins"
        assert key in manifest


def test_extension_id_matches_manifest() -> None:
    manifest = json.loads((ROOT / "extension" / "manifest.json").read_text())
    assert manifest["browser_specific_settings"]["gecko"]["id"] == install.EXTENSION_ID


def test_chromium_extension_id_matches_installer() -> None:
    import base64
    import hashlib

    manifest = json.loads((ROOT / "extension-chromium" / "manifest.json").read_text())
    digest = hashlib.sha256(base64.b64decode(manifest["key"])).digest()[:16]
    extension_id = "".join(chr(ord("a") + nibble) for byte in digest for nibble in divmod(byte, 16))
    assert extension_id == install.CHROMIUM_DEBUG_EXTENSION_ID
