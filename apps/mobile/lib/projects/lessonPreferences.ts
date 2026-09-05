import { readPrefFile, writePrefFile } from "@/lib/filePrefs";

export type LessonPreferences = { sound: boolean; voice: boolean };
type PreferenceOwner = { value?: LessonPreferences; pending: Promise<void> };
const owners = new Map<string, PreferenceOwner>();
const defaults = (): LessonPreferences => ({ sound: true, voice: false });

function ownerFor(path: string): PreferenceOwner {
  const existing = owners.get(path);
  if (existing) return existing;
  const owner = { pending: Promise.resolve() };
  owners.set(path, owner);
  return owner;
}

/** New visits see the latest accepted toggle, including writes still waiting on storage. */
export async function loadLessonPreferences(path: string | null): Promise<LessonPreferences> {
  if (!path) return defaults();
  const owner = ownerFor(path);
  if (owner.value) return owner.value;
  const raw = await readPrefFile(path);
  if (owner.value) return owner.value;
  try {
    const parsed = JSON.parse(raw ?? "null") as Partial<LessonPreferences> | null;
    owner.value = { sound: parsed?.sound !== false, voice: parsed?.voice === true };
  } catch {
    owner.value = defaults();
  }
  return owner.value;
}

/** Per-file ordering survives screen remounts; older writes cannot settle after a newer value. */
export function saveLessonPreferences(
  path: string | null,
  value: LessonPreferences,
): Promise<void> {
  if (!path) return Promise.resolve();
  const owner = ownerFor(path);
  owner.value = { ...value };
  const serialized = JSON.stringify(owner.value);
  owner.pending = owner.pending
    .then(() => writePrefFile(path, serialized))
    .catch(() => {
      /* Preferences remain usable in memory if local storage fails. */
    });
  return owner.pending;
}
