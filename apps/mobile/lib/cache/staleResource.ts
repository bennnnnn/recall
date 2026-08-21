export type StaleResourceEntry<T> = {
  data: T;
  fetchedAt: number;
};

type FetchOptions = {
  force?: boolean;
};

/**
 * Small typed cache for stale-while-revalidate resources.
 *
 * It owns timestamps and request deduplication only. Callers retain resource
 * policy (normalization, fallback behavior, and whether errors become null).
 */
export class StaleResourceCache<Key, Value> {
  private readonly entries = new Map<Key, StaleResourceEntry<Value>>();
  private readonly inflight = new Map<Key, Promise<Value>>();

  constructor(private readonly staleMs: number) {}

  get(key: Key): Value | undefined {
    return this.entries.get(key)?.data;
  }

  getEntry(key: Key): StaleResourceEntry<Value> | undefined {
    return this.entries.get(key);
  }

  getFetchedAt(key: Key): number | undefined {
    return this.entries.get(key)?.fetchedAt;
  }

  isFresh(key: Key, now = Date.now()): boolean {
    const entry = this.entries.get(key);
    return Boolean(entry && now - entry.fetchedAt < this.staleMs);
  }

  set(key: Key, data: Value, fetchedAt = Date.now()): Value {
    this.entries.set(key, { data, fetchedAt });
    return data;
  }

  update(key: Key, updater: (current: Value | undefined) => Value): Value {
    const current = this.entries.get(key);
    return this.set(key, updater(current?.data), current?.fetchedAt);
  }

  hasInflight(key: Key): boolean {
    return this.inflight.has(key);
  }

  invalidate(key: Key): void {
    this.entries.delete(key);
    this.inflight.delete(key);
  }

  clear(): void {
    this.entries.clear();
    this.inflight.clear();
  }

  async fetch(
    key: Key,
    loader: () => Promise<Value>,
    options?: FetchOptions,
  ): Promise<Value> {
    if (!options?.force && this.isFresh(key)) {
      return this.entries.get(key)!.data;
    }

    const pending = this.inflight.get(key);
    if (pending) return pending;

    const task = loader().then((data) => this.set(key, data));
    this.inflight.set(key, task);
    try {
      return await task;
    } finally {
      if (this.inflight.get(key) === task) {
        this.inflight.delete(key);
      }
    }
  }

  prefetch(key: Key, loader: () => Promise<Value>): void {
    if (this.isFresh(key) || this.hasInflight(key)) return;
    void this.fetch(key, loader).catch(() => undefined);
  }
}
