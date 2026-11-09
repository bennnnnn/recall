/**
 * Non-secret preference persistence, on the filesystem: Keychain writes fail on
 * unsigned simulator builds (errSecMissingEntitlement / -34018).
 */
import {
  deleteAsync,
  documentDirectory,
  getInfoAsync,
  readAsStringAsync,
  writeAsStringAsync,
} from "expo-file-system/legacy";

import { readTextFileSync } from "@/lib/syncFileRead";

export function prefFilePath(fileName: string): string | null {
  if (!documentDirectory) return null;
  return `${documentDirectory}${fileName}`;
}

export function safePrefUserId(userId: string): string {
  return userId.replace(/[^a-zA-Z0-9._-]/g, "_") || "default";
}

export async function readPrefFile(path: string | null): Promise<string | null> {
  if (!path) return null;
  try {
    const info = await getInfoAsync(path);
    if (!info.exists) return null;
    return await readAsStringAsync(path);
  } catch {
    return null;
  }
}

/** The pref read synchronously: only for what the first frame needs (`lib/launchPrefs.ts`). */
function readPrefFileSync(fileName: string): string | null {
  return readTextFileSync("document", fileName);
}

export async function writePrefFile(path: string | null, value: string): Promise<void> {
  if (!path) return;
  try {
    await writeAsStringAsync(path, value);
  } catch {
    /* best-effort — in-memory state from the caller still applies this session */
  }
}

export async function deletePrefFile(path: string | null): Promise<void> {
  if (!path) return;
  try {
    await deleteAsync(path, { idempotent: true });
  } catch {
    /* best-effort */
  }
}

/** One device preference in its own file, its value kept for the session once read or set. */
type FilePref<T> = {
  /** The saved value; `parse(null)`, the default, with no file. */
  get: () => Promise<T>;
  /** Saves `value`. Writes go out in turn and a newer one replaces any still waiting, so
   * the file ends as the last value set. */
  set: (value: T) => Promise<void>;
  /** The value this session has read or set; null before the first read. */
  peek: () => T | null;
  /** The saved value read synchronously, for the first frame (`lib/launchPrefs.ts`); null
   * with no file. */
  readSync: () => T | null;
  /** Forgets the session's value (tests). */
  reset: () => void;
};

/**
 * A preference kept in `fileName`. `parse` turns the file's text (null with no file) into a
 * value, falling back to the default on anything it does not know. A value set while the file
 * is read wins over what the read finds: each preference had this cache by hand, and a read
 * landing after a tap in Settings put the old value back for the session.
 */
export function createFilePref<T>(
  fileName: string,
  parse: (raw: string | null) => T,
  serialize: (value: T) => string = String,
): FilePref<T> {
  let cached: T | null = null;
  let generation = 0;
  let writes: Promise<void> = Promise.resolve();

  return {
    async get() {
      if (cached !== null) return cached;
      const expected = generation;
      const raw = await readPrefFile(prefFilePath(fileName));
      if (generation !== expected) return cached ?? parse(null);
      cached = parse(raw);
      return cached;
    },
    set(value) {
      cached = value;
      const expected = ++generation;
      writes = writes.then(async () => {
        if (generation === expected) await writePrefFile(prefFilePath(fileName), serialize(value));
      });
      return writes;
    },
    peek: () => cached,
    readSync() {
      if (cached !== null) return cached;
      const raw = readPrefFileSync(fileName);
      if (raw === null) return null;
      cached = parse(raw);
      return cached;
    },
    reset() {
      cached = null;
    },
  };
}
