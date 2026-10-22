# The single source of truth for developing, testing and packaging this repo.
# CI only ever calls the recipes below. Run `just` to list them.
#
# `uv` owns the virtualenv and every Python dependency (declared in pyproject.toml);
# `pre-commit` owns every lint check. Recipes below are thin wrappers over both.

set shell := ["bash", "-euo", "pipefail", "-c"]

venv := ".venv"
web_ext := "npx --yes web-ext@8"

default:
    @just --list

# --- setup -------------------------------------------------------------------

# Create the virtualenv and install the dev dependencies from pyproject.toml.
setup:
    uv sync

# --- checks ------------------------------------------------------------------

# Every lint check, via pre-commit: ruff check, ruff format, mypy, web-ext lint.
lint:
    uv run pre-commit run --all-files

# Unit tests for the native host (python) and the extension logic (node).
test-unit: test-host test-scripts test-extension

test-host:
    uv run pytest tests/host -v

test-scripts:
    uv run pytest tests/scripts -v

test-extension:
    node --test tests/extension/*.test.mjs

# Package in an isolated workspace and inspect every release artifact.
test-package:
    uv run pytest tests/package -v

# End-to-end tests: real headless Firefox and Chrome/Vivaldi (when available), real host.
test-e2e:
    uv run pytest tests/e2e -v

# Everything.
test: test-unit test-package test-e2e

# What CI runs on every push and pull request.
ci: lint test

# --- run it ------------------------------------------------------------------

# Register the host for Firefox, Chrome, Chromium, and Vivaldi.
# Pass --debug to allow the unpacked development build of the Chromium extension
# instead of the one installed from the Chrome Web Store.
install-host *flags:
    python3 host/install.py {{flags}}

uninstall-host:
    python3 host/install.py --uninstall

# Start Firefox with the extension loaded temporarily (needs install-host first).
run:
    {{web_ext}} run --source-dir extension

# Regenerate docs/screenshots/*.png (README embeds them).
screenshots:
    uv run playwright install chromium
    uv run python scripts/screenshots.py

# --- packaging ---------------------------------------------------------------

# The version declared in extension/manifest.json.
version:
    @python3 -c "import json; print(json.load(open('extension/manifest.json'))['version'])"

# Fail unless TAG (e.g. v1.2.3) matches the manifest version.
check-version tag:
    #!/usr/bin/env bash
    set -euo pipefail
    declared="v$(just version)"
    if [ "{{tag}}" != "$declared" ]; then
        echo "tag {{tag}} does not match extension/manifest.json version $declared" >&2
        exit 1
    fi

# Update every version field, commit the bump, and create the local release tag.
prepare-release version:
    uv run python scripts/prepare_release.py "{{version}}"

# Build dist/: Firefox and Chrome Web Store zips and the native host tarball. Optionally override
# (used for nightlies, e.g. `just package 0.1.0.42`).
package override="":
    #!/usr/bin/env bash
    set -euo pipefail
    version="{{override}}"
    version="${version:-$(just version)}"
    rm -rf build dist
    mkdir -p build/extension build/extension-chromium-web-store build/host dist
    cp -r extension/. build/extension/
    cp -r extension-chromium/. build/extension-chromium-web-store/
    python3 - "$version" <<'PY'
    import json, sys
    for path in (
        "build/extension/manifest.json",
        "build/extension-chromium-web-store/manifest.json",
    ):
        manifest = json.load(open(path))
        manifest["version"] = sys.argv[1]
        if "web-store" in path:
            manifest.pop("key", None)
        json.dump(manifest, open(path, "w"), indent=2)
    PY
    {{web_ext}} build --source-dir build/extension --artifacts-dir dist \
        --filename "send-to-other-browser-extension-${version}.zip" --overwrite-dest
    (cd build/extension-chromium-web-store && python3 -m zipfile -c \
        "../../dist/send-to-other-browser-chrome-web-store-${version}.zip" .)
    cp host/send_to_other_browser.py host/install.py build/host/
    tar -C build -czf "dist/send-to-other-browser-host-${version}.tar.gz" host
    ls -l dist

clean:
    rm -rf build dist {{venv}} .ruff_cache .mypy_cache .pytest_cache
