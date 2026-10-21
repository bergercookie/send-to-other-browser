import { getSelectedTabs, partitionTabs } from "../lib/sendable.js";
import { bindCloseAfterSend } from "../lib/settings.js";

const $ = (id) => document.getElementById(id);
const INSTALLATION_URL =
  "https://github.com/bergercookie/firefox-send-to-other-browser#installation";

function setStatus(text, kind = "") {
  const el = $("status");
  el.textContent = text;
  el.className = kind;
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

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

// `?tabIds=1,2` overrides the selection; it is the hook the e2e test uses
// (a popup opened in a tab cannot see the user's real tab selection).
async function loadTabs() {
  const ids = new URLSearchParams(location.search).get("tabIds");
  if (ids) {
    return Promise.all(ids.split(",").map((id) => browser.tabs.get(Number(id))));
  }
  return getSelectedTabs(browser.tabs);
}

async function main() {
  // The preference is sticky: it is restored from the extension's storage and
  // every change is written back to it.
  await bindCloseAfterSend($("close"), browser.storage.local);
  const tabs = await loadTabs();
  const { urls, skipped } = partitionTabs(tabs);
  $("summary").textContent =
    urls.length === 0
        ? "No sendable tabs selected."
        : `${plural(urls.length, "tab")} selected` +
        (skipped.length ? ` (${skipped.length} skipped: invalid URL)` : "") +
        ". Send to:";

  const reply = await browser.runtime.sendMessage({ type: "list" }).catch((e) => ({ ok: false, error: e.message }));
  if (!reply.ok) {
    setNativeHostError(reply.error);
    return;
  }
  if (reply.browsers.length === 0) {
    setStatus("No other supported browser (Vivaldi, Chrome, Chromium, …) found on this system.", "error");
    return;
  }

  for (const b of reply.browsers) {
    const button = document.createElement("button");
    button.textContent = b.name;
    button.dataset.browser = b.id;
    button.disabled = urls.length === 0;
    button.addEventListener("click", async () => {
      setStatus("Sending…");
      const result = await browser.runtime.sendMessage({
        type: "send",
        browserId: b.id,
        tabIds: tabs.map((t) => t.id),
        close: $("close").checked,
      });
      if (result.ok) {
        setStatus(`Sent ${plural(result.sent, "tab")} to ${b.name}.`, "ok");
      } else {
        setStatus(result.error, "error");
      }
    });
    $("browsers").append(button);
  }
}

main().catch((err) => setStatus(err.message, "error"));
