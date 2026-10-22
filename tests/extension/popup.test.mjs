import { test } from "node:test";
import assert from "node:assert/strict";
import { closePopupSoon, POPUP_CLOSE_DELAY_MS } from "../../extension/lib/popup.js";
import * as chromium from "../../extension-chromium/lib/popup.js";

for (const [name, module] of [
  ["firefox", { closePopupSoon, POPUP_CLOSE_DELAY_MS }],
  ["chromium", chromium],
]) {
  test(`${name}: the popup closes itself after a delay`, async () => {
    let closed = false;
    const closing = module.closePopupSoon({ delay: 10, close: () => (closed = true) });
    assert.equal(closed, false, "the popup stays open until the delay has passed");
    await closing;
    assert.equal(closed, true);
  });

  test(`${name}: the popup stays open when it is driven by the tests`, async () => {
    let closed = false;
    await module.closePopupSoon({
      search: "?tabIds=1,2",
      delay: 10,
      close: () => (closed = true),
    });
    assert.equal(closed, false);
  });

  test(`${name}: the popup closes itself by default`, async () => {
    assert.ok(module.POPUP_CLOSE_DELAY_MS > 0);
    let closed = false;
    const closing = module.closePopupSoon({ delay: module.POPUP_CLOSE_DELAY_MS, close: () => (closed = true) });
    await closing;
    assert.equal(closed, true);
  });
}
