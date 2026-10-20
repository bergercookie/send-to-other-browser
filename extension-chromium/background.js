import { getSelectedTabs } from "./lib/sendable.js";
import { listBrowsers } from "./lib/host.js";
import { sendTabs } from "./lib/send.js";

const MENU_PREFIX = "send:";

async function flashBadge(text, color) {
  await chrome.action.setBadgeBackgroundColor({ color });
  await chrome.action.setBadgeText({ text });
  setTimeout(() => chrome.action.setBadgeText({ text: "" }), 3000);
}

async function rebuildMenus() {
  await chrome.contextMenus.removeAll();
  let browsers = [];
  try {
    browsers = await listBrowsers(chrome.runtime);
  } catch (err) {
    console.warn("Native host unavailable, no tab menu entries:", err.message);
  }
  for (const browser of browsers) {
    chrome.contextMenus.create({
      id: MENU_PREFIX + browser.id,
      title: `Send to ${browser.name}`,
      contexts: ["tab"],
    });
  }
}

chrome.runtime.onInstalled.addListener(rebuildMenus);
chrome.runtime.onStartup.addListener(rebuildMenus);

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (!info.menuItemId.startsWith(MENU_PREFIX)) return;
  try {
    const tabs = await getSelectedTabs(chrome.tabs, tab);
    await sendTabs(chrome, info.menuItemId.slice(MENU_PREFIX.length), tabs);
    await flashBadge("✓", "#2e9e4f");
  } catch (err) {
    console.error(err);
    await flashBadge("!", "#d33");
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  let response;
  if (message.type === "list") {
    response = listBrowsers(chrome.runtime).then((browsers) => ({ ok: true, browsers }));
  } else if (message.type === "send") {
    response = Promise.all(message.tabIds.map((id) => chrome.tabs.get(id)))
      .then((tabs) => sendTabs(chrome, message.browserId, tabs, { close: message.close }))
      .then((result) => ({ ok: true, ...result }));
  } else {
    return false;
  }
  response.catch((err) => ({ ok: false, error: err.message })).then(sendResponse);
  return true;
});
