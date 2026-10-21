"""Resolve native browser executables hidden behind distribution launchers."""

import os
import re
import shutil
from pathlib import Path


def _is_native_firefox(path: Path) -> bool:
    try:
        resolved = path.resolve()
        with resolved.open("rb") as executable:
            return resolved.name in {"firefox", "firefox-bin"} and executable.read(4) == b"\x7fELF"
    except OSError:
        return False


def firefox_binary() -> str | None:
    """Return a native Firefox ELF, unwrapping common Snap and Nix launchers."""
    explicit = os.environ.get("FIREFOX_BIN")
    configured = explicit or shutil.which("firefox")
    if not configured:
        return None

    launcher = Path(configured)
    candidates = [launcher]
    try:
        source = launcher.read_text(errors="replace")
    except (OSError, UnicodeError):
        source = ""
    candidates.extend(
        Path(match.group(1))
        for match in re.finditer(r"""["'](/[^"'\n]+/(?:firefox|firefox-bin))["']""", source)
    )
    # An explicit FIREFOX_BIN must never silently resolve to an unrelated system Firefox.
    if not explicit:
        candidates += [
            Path("/snap/firefox/current/usr/lib/firefox/firefox"),
            Path("/snap/firefox/current/usr/lib/firefox/firefox-bin"),
            Path("/usr/lib/firefox/firefox"),
            Path("/usr/lib/firefox/firefox-bin"),
        ]
    return next((str(path.resolve()) for path in candidates if _is_native_firefox(path)), None)
