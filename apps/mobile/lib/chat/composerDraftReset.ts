const listeners = new Set<() => void>();

/** Chat registers so sign-out can wipe drafts even if index stays mounted. */
export function subscribeComposerDraftReset(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Drop unsent composer text for the outgoing account. No-op if chat is unmounted. */
export function resetComposerDraftsForAccount(): void {
  for (const listener of listeners) listener();
}

/** Test helper. */
export function resetComposerDraftResetListeners(): void {
  listeners.clear();
}
