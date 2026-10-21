import { test } from "node:test";
import assert from "node:assert/strict";
import {
  bindCloseAfterSend,
  getCloseAfterSend,
  setCloseAfterSend,
} from "../../extension/lib/settings.js";
import * as chromium from "../../extension-chromium/lib/settings.js";

function fakeStorage(initial = {}) {
  const data = { ...initial };
  return {
    data,
    async get(key) {
      return key in data ? { [key]: data[key] } : {};
    },
    async set(items) {
      Object.assign(data, items);
    },
  };
}

function fakeCheckbox(checked = false) {
  return {
    checked,
    listeners: [],
    addEventListener(type, listener) {
      this.listeners.push({ type, listener });
    },
    click() {
      this.checked = !this.checked;
      for (const { type, listener } of this.listeners) {
        if (type === "change") listener();
      }
    },
  };
}

test("getCloseAfterSend defaults to false", async () => {
  assert.equal(await getCloseAfterSend(fakeStorage()), false);
  assert.equal(await getCloseAfterSend(fakeStorage({ closeAfterSend: true })), true);
  assert.equal(await getCloseAfterSend(fakeStorage({ closeAfterSend: false })), false);
});

test("setCloseAfterSend stores a boolean", async () => {
  const storage = fakeStorage();
  await setCloseAfterSend(storage, true);
  assert.deepEqual(storage.data, { closeAfterSend: true });
  await setCloseAfterSend(storage, false);
  assert.equal(await getCloseAfterSend(storage), false);
});

test("bindCloseAfterSend restores the stored value and stores every change", async () => {
  const storage = fakeStorage({ closeAfterSend: true });
  const checkbox = fakeCheckbox();
  await bindCloseAfterSend(checkbox, storage);
  assert.equal(checkbox.checked, true);

  checkbox.click();
  assert.equal(checkbox.checked, false);
  assert.equal(await getCloseAfterSend(storage), false);

  checkbox.click();
  assert.equal(await getCloseAfterSend(storage), true);
});

test("bindCloseAfterSend leaves the checkbox alone when nothing is stored", async () => {
  const storage = fakeStorage();
  const checkbox = fakeCheckbox(true);
  await bindCloseAfterSend(checkbox, storage);
  assert.equal(checkbox.checked, false);
  assert.deepEqual(storage.data, {});
});

test("a change made while the stored value loads is neither lost nor overwritten", async () => {
  let release;
  const pending = new Promise((resolve) => {
    release = resolve;
  });
  const data = { closeAfterSend: false };
  const storage = {
    async get(key) {
      await pending;
      return { [key]: data[key] };
    },
    async set(items) {
      Object.assign(data, items);
    },
  };
  const checkbox = fakeCheckbox();
  const binding = bindCloseAfterSend(checkbox, storage);
  checkbox.click();
  release();
  await binding;
  assert.equal(checkbox.checked, true);
  assert.equal(await getCloseAfterSend(storage), true);
});

test("both builds store the preference under the same key", async () => {
  const storage = fakeStorage();
  await setCloseAfterSend(storage, true);
  assert.equal(await chromium.getCloseAfterSend(storage), true);
  await chromium.setCloseAfterSend(storage, false);
  assert.equal(await getCloseAfterSend(storage), false);
});
