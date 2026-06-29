/** Defer work until the UI is idle (replaces deprecated InteractionManager.runAfterInteractions). */
export function scheduleIdleTask(callback: () => void): () => void {
  if (typeof requestIdleCallback === "function") {
    const handle = requestIdleCallback(() => {
      callback();
    });
    return () => cancelIdleCallback(handle);
  }
  const handle = setTimeout(callback, 1);
  return () => clearTimeout(handle);
}
