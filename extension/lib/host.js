// Thin client for the native messaging host (host/send_to_other_browser.py).

export const HOST_NAME = "send_to_other_browser";

async function call(runtime, message) {
  const response = await runtime.sendNativeMessage(HOST_NAME, message);
  if (!response || !response.ok) {
    throw new Error((response && response.error) || "Native host returned no response");
  }
  return response;
}

/** @returns {Promise<{id: string, name: string, path: string}[]>} */
export async function listBrowsers(runtime) {
  let current = "firefox";
  if (typeof runtime.getBrowserInfo === "function") {
    const name = (await runtime.getBrowserInfo()).name.toLowerCase();
    if (name.includes("librewolf")) current = "librewolf";
    else if (name.includes("zen")) current = "zen";
  }
  return (await call(runtime, { action: "list" })).browsers.filter(
    (target) => target.id !== current,
  );
}

export function sendUrls(runtime, browserId, urls) {
  return call(runtime, { action: "send", browser: browserId, urls });
}
