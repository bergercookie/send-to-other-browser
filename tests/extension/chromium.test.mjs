import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const manifest = JSON.parse(
  await readFile(new URL("../../extension-chromium/manifest.json", import.meta.url)),
);

test("Chromium build is Manifest V3 with a module service worker", () => {
  assert.equal(manifest.manifest_version, 3);
  assert.deepEqual(manifest.background, { service_worker: "background.js", type: "module" });
  assert.ok(manifest.permissions.includes("nativeMessaging"));
  assert.ok(manifest.permissions.includes("contextMenus"));
  assert.ok(manifest.key);
  assert.equal(manifest.browser_specific_settings, undefined);
});

test("both manifests request the storage permission for the sticky setting", async () => {
  const firefox = JSON.parse(
    await readFile(new URL("../../extension/manifest.json", import.meta.url)),
  );
  for (const current of [firefox, manifest]) {
    assert.ok(current.permissions.includes("storage"));
  }
});

test("both popups restore the close-tabs preference from storage", async () => {
  for (const directory of ["extension", "extension-chromium"]) {
    const popup = await readFile(
      new URL(`../../${directory}/popup/popup.js`, import.meta.url),
      "utf8",
    );
    assert.match(popup, /bindCloseAfterSend\(\$\("close"\), (browser|chrome)\.storage\.local\)/);
  }
});

test("Chromium build contains every referenced extension asset", async () => {
  const paths = [
    manifest.background.service_worker,
    manifest.action.default_popup,
    ...Object.values(manifest.action.default_icon),
    ...Object.values(manifest.icons),
  ];
  await Promise.all(
    paths.map((path) => readFile(new URL(`../../extension-chromium/${path}`, import.meta.url))),
  );
});

test("Firefox and Chromium manifests expose raster logos", async () => {
  const firefox = JSON.parse(
    await readFile(new URL("../../extension/manifest.json", import.meta.url)),
  );
  for (const current of [firefox, manifest]) {
    assert.deepEqual(Object.keys(current.icons), ["48", "96", "128"]);
    for (const [size, path] of Object.entries(current.icons)) {
      assert.match(path, new RegExp(`icon-${size}\\.png$`));
      const png = await readFile(
        new URL(`../../${current === firefox ? "extension" : "extension-chromium"}/${path}`, import.meta.url),
      );
      assert.deepEqual([...png.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
      assert.equal(png.readUInt32BE(16), Number(size));
      assert.equal(png.readUInt32BE(20), Number(size));
    }
  }
});

test("both popups link native-host errors to the installation documentation", async () => {
  const expected = "https://github.com/bergercookie/firefox-send-to-other-browser#installation";
  for (const directory of ["extension", "extension-chromium"]) {
    const popup = await readFile(
      new URL(`../../${directory}/popup/popup.js`, import.meta.url),
      "utf8",
    );
    assert.ok(popup.includes(expected));
    assert.ok(popup.includes("installation documentation"));
    assert.ok(!popup.includes("just install-host"));
  }
});
