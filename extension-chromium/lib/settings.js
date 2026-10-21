// User preferences that outlive the popup (extension local storage).

const CLOSE_AFTER_SEND = "closeAfterSend";

export async function getCloseAfterSend(storage) {
  const stored = await storage.get(CLOSE_AFTER_SEND);
  return Boolean(stored && stored[CLOSE_AFTER_SEND]);
}

export async function setCloseAfterSend(storage, value) {
  await storage.set({ [CLOSE_AFTER_SEND]: Boolean(value) });
}

export async function bindCloseAfterSend(checkbox, storage) {
  let changed = false;
  checkbox.addEventListener("change", () => {
    changed = true;
    setCloseAfterSend(storage, checkbox.checked).catch((err) =>
      console.error("Cannot store the preference:", err.message),
    );
  });
  const stored = await getCloseAfterSend(storage);
  if (!changed) {
    checkbox.checked = stored;
  }
}
