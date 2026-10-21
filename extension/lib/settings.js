// User preferences that outlive the popup (extension local storage).

const CLOSE_AFTER_SEND = "closeAfterSend";

/**
 * Whether the tabs that were sent should be closed afterwards.
 * Defaults to false when nothing has been stored yet.
 */
export async function getCloseAfterSend(storage) {
  const stored = await storage.get(CLOSE_AFTER_SEND);
  return Boolean(stored && stored[CLOSE_AFTER_SEND]);
}

/** Remember the "close tabs after sending" preference. */
export async function setCloseAfterSend(storage, value) {
  await storage.set({ [CLOSE_AFTER_SEND]: Boolean(value) });
}

/**
 * Show the stored preference in `checkbox` and store every change the user makes.
 * The listener is attached first, so a change made while the stored value is
 * still loading is neither lost nor overwritten by it.
 */
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
