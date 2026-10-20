import { getSelectedTabs, partitionTabs } from "../lib/sendable.js";

const $ = (id) => document.getElementById(id);
const plural = (count, word) => `${count} ${word}${count === 1 ? "" : "s"}`;
const INSTALLATION_URL =
  "https://github.com/bergercookie/firefox-send-to-other-browser#installation";

function setStatus(text, kind = "") {
  $("status").textContent = text;
  $("status").className = kind;
}

function setNativeHostError(error) {
  const link = document.createElement("a");
  link.href = INSTALLATION_URL;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = "installation documentation";
  const status = $("status");
  status.replaceChildren(`Cannot reach the native host: ${error} See the `, link, ".");
  status.className = "error";
}

async function loadTabs() {
  const ids = new URLSearchParams(location.search).get("tabIds");
  if (ids) return Promise.all(ids.split(",").map((id) => chrome.tabs.get(Number(id))));
  return getSelectedTabs(chrome.tabs);
}

async function main() {
  const tabs = await loadTabs();
  const { urls, skipped } = partitionTabs(tabs);
  $("summary").textContent =
    urls.length === 0
      ? "No sendable tabs selected."
      : `${plural(urls.length, "tab")} selected` +
        (skipped.length ? ` (${skipped.length} skipped: invalid URL)` : "") +
        ". Send to:";

  const reply = await chrome.runtime
    .sendMessage({ type: "list" })
    .catch((error) => ({ ok: false, error: error.message }));
  if (!reply.ok) {
    setNativeHostError(reply.error);
    return;
  }
  if (reply.browsers.length === 0) {
    setStatus("No other supported browser (Firefox, Vivaldi, Chrome, …) found on this system.", "error");
    return;
  }

  for (const browser of reply.browsers) {
    const button = document.createElement("button");
    button.textContent = browser.name;
    button.dataset.browser = browser.id;
    button.disabled = urls.length === 0;
    button.addEventListener("click", async () => {
      setStatus("Sending…");
      const result = await chrome.runtime.sendMessage({
        type: "send",
        browserId: browser.id,
        tabIds: tabs.map((tab) => tab.id),
        close: $("close").checked,
      });
      setStatus(
        result.ok ? `Sent ${plural(result.sent, "tab")} to ${browser.name}.` : result.error,
        result.ok ? "ok" : "error",
      );
    });
    $("browsers").append(button);
  }
}

main().catch((error) => setStatus(error.message, "error"));
