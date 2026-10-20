import { test } from "node:test";
import assert from "node:assert/strict";
import { sendTabs } from "../../extension/lib/send.js";
import { listBrowsers, HOST_NAME } from "../../extension/lib/host.js";

function fakeApi(responder) {
  const api = {
    messages: [],
    removed: [],
    runtime: {
      async sendNativeMessage(name, message) {
        api.messages.push({ name, message });
        return responder(message);
      },
    },
    tabs: {
      async remove(ids) {
        api.removed.push(...ids);
      },
    },
  };
  return api;
}

const tabs = [
  { id: 1, url: "https://a.example/" },
  { id: 2, url: "about:addons" },
  { id: 3, url: "https://b.example/" },
];

test("sendTabs sends URLs with different schemes to the chosen browser", async () => {
  const api = fakeApi(() => ({ ok: true }));
  const result = await sendTabs(api, "vivaldi", tabs);
  assert.deepEqual(api.messages, [
    {
      name: HOST_NAME,
      message: {
        action: "send",
        browser: "vivaldi",
        urls: ["https://a.example/", "about:addons", "https://b.example/"],
      },
    },
  ]);
  assert.deepEqual(result, { sent: 3, skipped: 0, closed: 0 });
  assert.deepEqual(api.removed, []);
});

test("sendTabs closes the sent tabs (not the skipped ones) when asked", async () => {
  const api = fakeApi(() => ({ ok: true }));
  const result = await sendTabs(api, "chrome", tabs, { close: true });
  assert.deepEqual(api.removed, [1, 2, 3]);
  assert.equal(result.closed, 3);
});

test("sendTabs rejects when nothing is sendable and does not call the host", async () => {
  const api = fakeApi(() => ({ ok: true }));
  await assert.rejects(sendTabs(api, "chrome", [{ id: 4, url: "not a URL" }]), /valid URL/);
  assert.equal(api.messages.length, 0);
});

test("sendTabs surfaces host errors and does not close tabs", async () => {
  const api = fakeApi(() => ({ ok: false, error: "browser 'chrome' not found on this system" }));
  await assert.rejects(sendTabs(api, "chrome", tabs, { close: true }), /not found/);
  assert.deepEqual(api.removed, []);
});

test("listBrowsers returns the host's list and errors on an empty reply", async () => {
  const vivaldi = { id: "vivaldi", name: "Vivaldi", path: "/usr/bin/vivaldi" };
  const firefox = { id: "firefox", name: "Mozilla Firefox", path: "/usr/bin/firefox" };
  assert.deepEqual(
    await listBrowsers(fakeApi(() => ({ ok: true, browsers: [firefox, vivaldi] })).runtime),
    [vivaldi],
  );
  await assert.rejects(listBrowsers(fakeApi(() => undefined).runtime), /no response/);
});

test("listBrowsers hides the current Firefox-family browser", async () => {
  const browsers = [
    { id: "firefox", name: "Mozilla Firefox" },
    { id: "zen", name: "Zen Browser" },
    { id: "librewolf", name: "LibreWolf" },
  ];
  for (const [name, hidden] of [
    ["Firefox", "firefox"],
    ["Zen Browser", "zen"],
    ["LibreWolf", "librewolf"],
  ]) {
    const runtime = fakeApi(() => ({ ok: true, browsers })).runtime;
    runtime.getBrowserInfo = async () => ({ name });
    assert.deepEqual(
      (await listBrowsers(runtime)).map((browser) => browser.id),
      browsers.map((browser) => browser.id).filter((id) => id !== hidden),
    );
  }
});
