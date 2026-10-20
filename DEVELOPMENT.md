# Development

Development requires Python 3, Node.js 18+, [uv](https://docs.astral.sh/uv/), and
[`just`](https://just.systems). The E2E suites additionally require Firefox or a Chromium-family
browser and its matching WebDriver. If `just` is not installed, bootstrap the pinned release:

```sh
scripts/install-just.sh          # installs to ~/.local/bin; override JUST_VERSION or pass a directory
```

Everything goes through the [`justfile`](justfile) (`just` lists recipes); CI calls the same recipes.

Python tooling is managed from [`pyproject.toml`](pyproject.toml), which is the single source of
truth for the dependencies (dev group) and the pytest, mypy, and Ruff configuration. `just setup`
creates `.venv` and installs it; every command below runs inside that environment via `uv run`.

All lint checks live in [`.pre-commit-config.yaml`](.pre-commit-config.yaml): `ruff check`,
`ruff format`, `mypy`, and `web-ext lint`. `just lint` runs all of them over the whole tree. Run
`uv run pre-commit install` once if you also want them on every commit.

## Load the extension locally

Register the native host before testing browser-to-browser sending:

```sh
python3 host/install.py
```

### Firefox

Start a temporary Firefox profile with the extension loaded:

```sh
just run
```

Alternatively, load it from Firefox itself:

1. Open `about:debugging#/runtime/this-firefox`.
2. Select **Load Temporary Add-on…**.
3. Choose `extension/manifest.json` from this repository.

Firefox removes temporary extensions when the browser exits, so repeat these steps after restarting
it. Reload the extension from the debugging page after changing JavaScript or the manifest.

### Chrome, Chromium, or Vivaldi

1. Open `chrome://extensions` in Chrome or Chromium, or `vivaldi://extensions` in Vivaldi.
2. Enable **Developer mode**.
3. Select **Load unpacked**.
4. Choose the repository's `extension-chromium/` directory.

Use the extension's **Reload** button on that page after changing its JavaScript or manifest.

## Commands

| Recipe | What |
| --- | --- |
| `just setup` | `uv sync`: create `.venv` and install the development dependencies |
| `just lint` | Run every lint check through pre-commit |
| `just test-unit` | Run Python host and Node.js extension unit tests |
| `just test-package` | Run `just package` in isolation and verify all release archives |
| `just test-e2e` | Run Firefox and Chromium-family browser E2E suites; unavailable browser suites skip |
| `just ci` | Run lint, unit tests, and E2E tests |
| `just package [version]` | Build the Firefox, Chrome Web Store, and host archives in `dist/` |
| `just screenshots` | Install Playwright Chromium and regenerate `docs/screenshots/*.png` |

Set `FIREFOX_BIN`, `CHROME_BIN`, `VIVALDI_BIN`, or `CHROMIUM_BIN` to select browser binaries for
the E2E suites. Set `CHROMEDRIVER` when the matching driver is not available on `PATH`.

## Workflows

- `ci.yml`: runs `just ci` on pushes to `main`/`master` and pull requests.
- `release.yml`: for `v*` tags on `main`/`master`, validates the manifest version, runs the test
  suite, packages the artifacts, submits the Firefox extension to AMO, and creates a GitHub release.
- `nightly.yml`: publishes the rolling `nightly` prerelease after changes to `main`/`master`, with
  a daily scheduled run as a safety net.
- `screenshots.yml`: on demand (`workflow_dispatch`), regenerates and commits the screenshots.

Upload `send-to-other-browser-chrome-web-store-<version>.zip` to the Chrome Web Store. It omits
the development `key` so the store can preserve the existing item's extension ID. For development,
load `extension-chromium/` unpacked; its manifest retains the key that gives local installs the
stable ID allowed by the native host.

To enable Firefox publishing, create AMO API credentials and add them to the GitHub repository as
the `AMO_JWT_ISSUER` and `AMO_JWT_SECRET` Actions secrets. Pushing a version tag such as `v0.2.0`
then submits `extension/` to the listed AMO channel; the tag must match the version in
`extension/manifest.json`.
