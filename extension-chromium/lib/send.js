import { partitionTabs } from "./sendable.js";
import { sendUrls } from "./host.js";

export async function sendTabs(api, browserId, tabs, { close = false } = {}) {
  const { urls, sendableTabs, skipped } = partitionTabs(tabs);
  if (urls.length === 0) {
    throw new Error("None of the selected tabs has a valid URL that can be sent.");
  }
  await sendUrls(api.runtime, browserId, urls);
  let closed = 0;
  if (close) {
    await api.tabs.remove(sendableTabs.map((tab) => tab.id));
    closed = sendableTabs.length;
  }
  return { sent: urls.length, skipped: skipped.length, closed };
}
