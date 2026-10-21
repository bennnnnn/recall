/**
 * When a sync the app runs after sign-in last succeeded on this phone (push
 * registration, the location label), per account. A file pref, so a cold start
 * can skip work done a moment ago instead of repeating it every launch.
 * Sign-out forgets them: the next sign-in, of any account, syncs afresh.
 */
import { deletePrefFile, prefFilePath, readPrefFile, writePrefFile } from "@/lib/filePrefs";

const SYNC_KINDS = ["push", "location"] as const;
type SyncKind = (typeof SYNC_KINDS)[number];

type SyncRecord = { account: string; variant: string; at: number };

function filePath(kind: SyncKind): string | null {
  return prefFilePath(`recall.synced-${kind}.json`);
}

/**
 * When `kind` last synced for `account` (with the same `variant`, such as the
 * push setting it registered), if that was less than `maxAgeMs` ago; else null.
 */
export async function recentSyncAt(
  kind: SyncKind,
  account: string,
  maxAgeMs: number,
  variant = "",
  now = Date.now(),
): Promise<number | null> {
  const raw = await readPrefFile(filePath(kind));
  if (raw === null) return null;
  try {
    const record = JSON.parse(raw) as Partial<SyncRecord>;
    if (record.account !== account || record.variant !== variant) return null;
    if (typeof record.at !== "number") return null;
    const age = now - record.at;
    // A clock set back makes the age negative: not trusted as recent.
    return age >= 0 && age < maxAgeMs ? record.at : null;
  } catch {
    return null;
  }
}

export function recordSync(
  kind: SyncKind,
  account: string,
  variant = "",
  at = Date.now(),
): Promise<void> {
  const record: SyncRecord = { account, variant, at };
  return writePrefFile(filePath(kind), JSON.stringify(record));
}

export function forgetSync(kind: SyncKind): Promise<void> {
  return deletePrefFile(filePath(kind));
}

/** Sign-out. */
export async function forgetSyncRecords(): Promise<void> {
  await Promise.all(SYNC_KINDS.map(forgetSync));
}
