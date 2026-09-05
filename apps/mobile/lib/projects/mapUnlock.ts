const seeded = new Set<string>();
const snapshot = new Map<string, ReadonlySet<string>>();
const pending = new Map<string, Set<string>>();

/** Done groups that finished since this class's map was last observed. First look is silent. */
export function syncMapUnlocks(projectId: string, doneTitles: readonly string[]): string[] {
  const next = new Set(doneTitles);
  if (!seeded.has(projectId)) {
    seeded.add(projectId);
    snapshot.set(projectId, next);
    return [...(pending.get(projectId) ?? [])];
  }
  const prev = snapshot.get(projectId) ?? new Set();
  const open = pending.get(projectId) ?? new Set();
  for (const title of doneTitles) {
    if (!prev.has(title)) open.add(title);
  }
  snapshot.set(projectId, next);
  pending.set(projectId, open);
  return [...open];
}

/** Drop titles from the pending set so later map visits do not replay the unlock. */
export function acknowledgeMapUnlocks(projectId: string, titles: readonly string[]): void {
  const open = pending.get(projectId);
  if (!open) return;
  for (const title of titles) open.delete(title);
}

export function resetMapUnlockState(): void {
  seeded.clear();
  snapshot.clear();
  pending.clear();
}
