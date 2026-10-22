// Closing the popup once the tabs have been sent.

export const POPUP_CLOSE_DELAY_MS = 700;

/**
 * Close the popup after a short delay, so the confirmation stays readable.
 * Only the action popup closes itself; a page opened with the `?tabIds=` override
 * (the e2e tests, the screenshot script) is left alone.
 */
export function closePopupSoon({
  search = "",
  delay = POPUP_CLOSE_DELAY_MS,
  close = () => window.close(),
} = {}) {
  if (new URLSearchParams(search).has("tabIds")) {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    setTimeout(() => {
      close();
      resolve();
    }, delay);
  });
}
