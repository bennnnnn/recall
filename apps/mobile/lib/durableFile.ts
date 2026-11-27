/**
 * A small text file the phone must not lose: an unsent draft, the purchase hold that keeps a
 * second charge away. It lives in the documents directory, which the OS never empties; the
 * cache directory (`lib/cache/cacheFile.ts`) it may purge whenever storage runs low.
 *
 * A write replaces the file whole or not at all, so a kill mid-write keeps the last one. iOS
 * already writes that way (the native write is `Data.write(.atomic)`). Android truncates the
 * file and writes it in place, so there each write goes to `<name>.tmp` first and is renamed
 * over the file (`File.renameTo`, one atomic rename). A temp file a kill left behind is never
 * read, and the next write replaces it.
 *
 * Backups. Android backs up none of these files: expo-secure-store's Auto Backup rules include
 * only shared preferences (`lib/__tests__/appStoreConfig.test.ts`). iOS backs up the documents
 * directory, and nothing Expo offers can exclude a file from it (no `NSURLIsExcludedFromBackupKey`
 * in expo-file-system; Application Support is not reachable; Caches is the purgeable directory
 * these files left). So on iOS an unsent draft rides in the user's own backup, a deliberate
 * choice: each file names the account that wrote it and is read only for that account, and the
 * purchase hold is written on Android only. Excluding it on iOS needs a native module.
 */
import { Platform } from "react-native";
import {
  cacheDirectory,
  deleteAsync,
  documentDirectory,
  getInfoAsync,
  moveAsync,
  readAsStringAsync,
  writeAsStringAsync,
} from "expo-file-system/legacy";

import { reportFailure } from "@/lib/sentry";

type DurableFile = {
  /** The file's text; null when there is none or it cannot be read. */
  read: () => Promise<string | null>;
  write: (contents: string) => Promise<void>;
  /** Deletes the file, its temp and any copy the cache directory still holds. */
  clear: () => Promise<void>;
};

const TEMP_SUFFIX = ".tmp";

/** A file that could not be read or written: the caller goes on with what it has in memory. */
function reportFileFailure(error: unknown): void {
  reportFailure("durable_file", error);
}

/** Writes `contents` to `path` so that a kill at any point leaves the old file or the new one. */
export async function writeFileAtomically(path: string, contents: string): Promise<void> {
  if (Platform.OS !== "android") {
    await writeAsStringAsync(path, contents);
    return;
  }
  const temp = `${path}${TEMP_SUFFIX}`;
  await writeAsStringAsync(temp, contents);
  await moveAsync({ from: temp, to: path });
}

async function exists(path: string): Promise<boolean> {
  return (await getInfoAsync(path)).exists;
}

/**
 * Earlier versions kept the file in the cache directory: the first change or read of a run
 * takes that copy over when this one has no file yet, then deletes it. A copy that cannot be
 * read stays for the next run.
 */
async function adoptCacheCopy(path: string, cachePath: string): Promise<void> {
  if (!(await exists(cachePath))) return;
  if (!(await exists(path))) await writeFileAtomically(path, await readAsStringAsync(cachePath));
  await deleteAsync(cachePath, { idempotent: true });
}

/**
 * The durable file `fileName`. `formerCacheName` names the cache-directory file earlier
 * versions wrote it to. Writes and clears run in the order they were asked for, and reads
 * wait for them, as `cacheFile` does.
 */
export function durableFile(fileName: string, formerCacheName?: string): DurableFile {
  const path = documentDirectory ? `${documentDirectory}${fileName}` : null;
  const cachePath = formerCacheName && cacheDirectory ? `${cacheDirectory}${formerCacheName}` : null;
  let pending: Promise<void> | null = null;
  const enqueue = (change: (filePath: string) => Promise<void>): Promise<void> => {
    if (!path) return Promise.resolve();
    pending ??= cachePath ? adoptCacheCopy(path, cachePath).catch(reportFileFailure) : Promise.resolve();
    const result = pending.then(() => change(path)).catch(reportFileFailure);
    pending = result;
    return result;
  };
  return {
    async read() {
      if (!path) return null;
      await enqueue(async () => {});
      try {
        return (await exists(path)) ? await readAsStringAsync(path) : null;
      } catch (error) {
        reportFileFailure(error);
        return null;
      }
    },
    write: (contents) => enqueue((filePath) => writeFileAtomically(filePath, contents)),
    clear: () =>
      enqueue(async (filePath) => {
        const paths = [filePath, `${filePath}${TEMP_SUFFIX}`, ...(cachePath ? [cachePath] : [])];
        await Promise.all(paths.map((target) => deleteAsync(target, { idempotent: true })));
      }),
  };
}
