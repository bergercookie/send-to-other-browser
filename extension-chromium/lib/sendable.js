export function isSendableUrl(url) {
  try {
    return Boolean(new URL(url).protocol);
  } catch {
    return false;
  }
}

export function partitionTabs(tabs) {
  const sendableTabs = [];
  const skipped = [];
  const urls = [];
  for (const tab of tabs) {
    if (isSendableUrl(tab.url)) {
      sendableTabs.push(tab);
      if (!urls.includes(tab.url)) urls.push(tab.url);
    } else {
      skipped.push(tab);
    }
  }
  return { urls, sendableTabs, skipped };
}

export async function getSelectedTabs(tabsApi, clickedTab = null) {
  const query = clickedTab
    ? { highlighted: true, windowId: clickedTab.windowId }
    : { highlighted: true, currentWindow: true };
  const highlighted = await tabsApi.query(query);
  if (clickedTab && !highlighted.some((tab) => tab.id === clickedTab.id)) return [clickedTab];
  return highlighted;
}
