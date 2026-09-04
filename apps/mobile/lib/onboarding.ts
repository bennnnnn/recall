/** Onboarding is a non-secret device preference; auth credentials stay in SecureStore. */
import {
  deleteLegacySecureStore,
  prefFilePath,
  readLegacySecureStore,
  readPrefFile,
  writePrefFile,
} from "@/lib/filePrefs";

const LEGACY_KEY = "recall_onboarded";
const FILE_NAME = "recall.onboarded.txt";

let cached: boolean | null = null;
let generation = 0;
let writes: Promise<void> = Promise.resolve();

function persist(value: boolean, expectedGeneration: number): Promise<void> {
  writes = writes.then(async () => {
    if (generation !== expectedGeneration) return;
    await writePrefFile(prefFilePath(FILE_NAME), value ? "1" : "0");
  });
  return writes;
}

export async function getOnboarded(): Promise<boolean> {
  if (cached !== null) return cached;
  const expectedGeneration = generation;
  const stored = await readPrefFile(prefFilePath(FILE_NAME));
  const legacy = stored === null ? await readLegacySecureStore(LEGACY_KEY) : null;
  if (generation !== expectedGeneration) return cached ?? false;
  cached = (stored ?? legacy) === "1";
  if (stored === null && legacy !== null) {
    await persist(cached, expectedGeneration);
  }
  return cached;
}

export async function setOnboarded(): Promise<void> {
  cached = true;
  await persist(true, ++generation);
}

export async function clearOnboarded(): Promise<void> {
  cached = false;
  // Keep a false value on disk so a failed legacy-key deletion cannot revive onboarding.
  await persist(false, ++generation);
  await deleteLegacySecureStore(LEGACY_KEY);
}
