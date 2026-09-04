type Flusher = () => Promise<void>;

const flushers = new Set<Flusher>();

/** EmailCard registers so a follow-up send can flush an in-progress edit. */
export function registerEmailDraftFlusher(flush: Flusher): () => void {
  flushers.add(flush);
  return () => {
    flushers.delete(flush);
  };
}

export async function flushEmailDrafts(): Promise<void> {
  await Promise.all(
    [...flushers].map((flush) =>
      flush().catch(() => {
        /* persist surfaces its own error */
      }),
    ),
  );
}
