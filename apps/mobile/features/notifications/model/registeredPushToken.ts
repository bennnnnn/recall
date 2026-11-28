/**
 * The Expo push token this install last registered with the server, kept on the device. A
 * sign-out hands the server this device's token so its reminders stop reaching this lock
 * screen, but with notifications turned off in the phone's Settings the token could no longer be
 * read (and the switch is no longer turned off on a refusal): the old account's token stayed on
 * the server, and once notifications were allowed again its reminders showed here. The token is
 * the install's, the same for every account, so it is not cleared at sign-out; it is forgotten
 * once the server has removed it (push switched off). Never registered: nothing is sent.
 *
 * It lives in the secure store, this phone only (`lib/secureStore.ts`), as the installation id
 * does: a token in the documents directory travelled to a new iPhone in a backup, and a sign-out
 * there handed the server the old phone's token, which then lost its reminders. A reinstall
 * clears it, after the logout it owes for the old session has taken it. Earlier versions kept it
 * in a documents file; its first read moves that token into the secure store.
 */
import { deletePrefFile, prefFilePath, readPrefFile } from "@/lib/filePrefs";
import { SECURE_KEYS, secureDelete, secureGet, secureSet } from "@/lib/secureStore";
import { reportFailure } from "@/lib/sentry";

const LEGACY_FILE = "recall.push-token.txt";

/** The token this run set or read: a write that failed still applies for the run. Undefined before either. */
let known: string | null | undefined;
/** Writes go out in turn, so the store ends as the last token set. */
let writes: Promise<void> = Promise.resolve();

async function readStored(): Promise<string | null> {
  const stored = await secureGet(SECURE_KEYS.registeredPushToken);
  if (stored) return stored;
  const path = prefFilePath(LEGACY_FILE);
  const legacy = (await readPrefFile(path))?.trim() || null;
  if (legacy) {
    await secureSet(SECURE_KEYS.registeredPushToken, legacy);
    await deletePrefFile(path);
  }
  return legacy;
}

/** A read that fails reads as none, and a failed write keeps the token in memory for this run:
 * neither throws. */
export async function readRegisteredPushToken(): Promise<string | null> {
  if (known !== undefined) return known;
  await writes;
  if (known !== undefined) return known;
  try {
    const stored = await readStored();
    known ??= stored;
    return known;
  } catch (error) {
    reportFailure("push_token_store", error);
    return null;
  }
}

export function rememberRegisteredPushToken(token: string | null): Promise<void> {
  known = token;
  writes = writes.then(async () => {
    if (known !== token) return;
    try {
      if (token) await secureSet(SECURE_KEYS.registeredPushToken, token);
      else await secureDelete(SECURE_KEYS.registeredPushToken);
    } catch (error) {
      reportFailure("push_token_store", error);
    }
  });
  return writes;
}
