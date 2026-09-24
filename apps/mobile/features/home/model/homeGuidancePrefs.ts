import { prefFilePath, readPrefFile, safePrefUserId, writePrefFile } from "@/lib/filePrefs";

const cached = new Map<string, boolean>();
const reads = new Map<string, Promise<boolean>>();

function filePath(userId: string): string | null {
  return prefFilePath(`recall.home-guidance.${safePrefUserId(userId)}.txt`);
}

/** Whether this account has already used chat and no longer needs starter chips. */
export async function isHomeGuidanceRetired(userId: string): Promise<boolean> {
  const known = cached.get(userId);
  if (known !== undefined) return known;

  const pending = reads.get(userId);
  if (pending) return pending;

  const reading = readPrefFile(filePath(userId)).then((stored) => {
    const retired = stored === "1";
    // A send may retire guidance while this read is in flight. Never revive it.
    if (!cached.get(userId)) cached.set(userId, retired);
    reads.delete(userId);
    return cached.get(userId) ?? retired;
  });
  reads.set(userId, reading);
  return reading;
}

/** Retire generic starter chips immediately; persistence is best-effort. */
export async function retireHomeGuidance(userId: string): Promise<void> {
  cached.set(userId, true);
  await writePrefFile(filePath(userId), "1");
}

