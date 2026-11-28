/**
 * The one door to the secure store (iOS Keychain, Android Keystore). Every read, write and
 * delete passes the same options:
 *
 * - `AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY`: an item never leaves this phone. Without it the
 *   30-day sign-in went to a new iPhone in an iCloud backup or Quick Start; with both phones
 *   using it, refresh-token reuse signed out every session. A restored installation id made
 *   two phones delete each other's push token.
 * - iOS keeps the Keychain when the app is deleted, so a reinstall signed straight back in.
 *   An install marker in the documents directory (which goes with the app) tells a reinstall,
 *   and the session and installation id are cleared before anything reads them.
 *
 * Every call waits for that launch check (`installChecked`). The rule it follows:
 *
 * | marker | Keychain "ran" item | what this is | done |
 * | --- | --- | --- | --- |
 * | yes | yes | an ordinary launch | nothing |
 * | no | no | first launch of this version: an upgrade, or a new install | each item rewritten in the new class |
 * | no | yes | this version ran, then its files went: a reinstall | session, installation id and registered push token cleared, the session's logout (with that token) owed to the server |
 * | yes | no | a backup restored onto another phone, or a first launch cut short | items rewritten, nothing cleared |
 *
 * The marker is written before the "ran" item, so a launch killed between the two reads as
 * the last row next time, never as a reinstall: an upgrade can never sign anyone out. Any
 * read that fails (the Keychain locked in a background launch) changes nothing; the next call
 * looks again. A reinstall deletes "ran" once it has cleared, before it writes the marker: a
 * marker that cannot be written (a full disk) then leaves "no marker, no ran", so no later
 * launch reads the same reinstall again and deletes a sign-in made after the clear.
 */
import * as SecureStore from "expo-secure-store";

import { reportFailure } from "@/lib/sentry";

/** Every item the app keeps in the secure store. */
export const SECURE_KEYS = {
  /** The signed-in session's token pair (`lib/auth.ts`). */
  session: "recall_session_v1",
  /** Logouts the server has not heard yet (`lib/pendingLogout.ts`). */
  pendingLogouts: "recall_pending_logouts_v1",
  /** This install's id, for push token re-bind checks (`lib/installationId.ts`). */
  installationId: "recall_installation_id_v1",
  /** The Expo push token this install last registered (`features/notifications/model/registeredPushToken.ts`). */
  registeredPushToken: "recall_push_token_v1",
} as const;

/** Written once this version has run on this phone; it outlives a reinstall, the marker does not. */
const RAN_KEY = "recall_install_v1";
const RAN_VALUE = "1";
const MARKER_FILE = "recall.install-marker.txt";

/** Items an earlier version wrote in the default (backed-up) class. */
const MIGRATED_KEYS = [SECURE_KEYS.session, SECURE_KEYS.pendingLogouts] as const;
/** What a reinstall forgets. Owed logouts stay: they still revoke sessions on the server. */
const CLEARED_ON_REINSTALL = [SECURE_KEYS.session, SECURE_KEYS.installationId, SECURE_KEYS.registeredPushToken] as const;
/** As many owed logouts as `lib/pendingLogout.ts` keeps. */
const MAX_PENDING_LOGOUTS = 5;

const SECURE_STORE_OPTIONS: SecureStore.SecureStoreOptions = {
  keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY,
};

const keychain = {
  get: (key: string) => SecureStore.getItemAsync(key, SECURE_STORE_OPTIONS),
  set: (key: string, value: string) => SecureStore.setItemAsync(key, value, SECURE_STORE_OPTIONS),
  delete: (key: string) => SecureStore.deleteItemAsync(key, SECURE_STORE_OPTIONS),
};

/**
 * Rewrites each item in the new class. iOS finds an item whatever its class (the class is
 * not part of the Keychain query), and a write over an existing item updates its class in
 * place: expo-secure-store's `set` meets `errSecDuplicateItem` and calls `update`, which puts
 * `kSecAttrAccessible` in `SecItemUpdate`'s attributes whenever `keychainAccessible` is passed
 * (`ios/SecureStoreModule.swift`, 58.0.2). So the value is never deleted first, and running it
 * again is harmless.
 */
async function migrateItems(): Promise<void> {
  for (const key of MIGRATED_KEYS) {
    const value = await keychain.get(key);
    if (value !== null) await keychain.set(key, value);
  }
}

/** A stored record read as JSON; null when there is none or it is not JSON (reported). */
function readJson(raw: string | null): unknown {
  if (raw === null) return null;
  try {
    return JSON.parse(raw);
  } catch (error) {
    reportFailure("install_check", error);
    return null;
  }
}

/** The stored session's token pair, or null (none, signed out, or not a session). */
function tokenPair(raw: string | null): { accessToken: string; refreshToken: string | null } | null {
  const pair = readJson(raw) as { accessToken?: unknown; refreshToken?: unknown } | null;
  if (typeof pair?.accessToken !== "string" || !pair.accessToken) return null;
  return { accessToken: pair.accessToken, refreshToken: typeof pair.refreshToken === "string" ? pair.refreshToken : null };
}

/**
 * The session a deleted app left: its logout is written down as owed (`lib/pendingLogout.ts`
 * sends it at start), so the server ends it and forgets this device's push token for that
 * account, instead of keeping both for the refresh token's 30 days. Then it is cleared.
 */
async function oweLogout(session: { accessToken: string; refreshToken: string | null }): Promise<void> {
  const parsed = readJson(await keychain.get(SECURE_KEYS.pendingLogouts));
  const owed = (Array.isArray(parsed) ? parsed : []) as { accessToken?: unknown }[];
  if (owed.some((entry) => entry.accessToken === session.accessToken)) return;
  // The token the deleted app registered, cleared below: the logout takes it off that account
  // even while notifications are off and no token can be read.
  const pushToken = (await keychain.get(SECURE_KEYS.registeredPushToken)) || null;
  const entry = { ...session, pushToken, queuedAt: Date.now() };
  await keychain.set(SECURE_KEYS.pendingLogouts, JSON.stringify([...owed, entry].slice(-MAX_PENDING_LOGOUTS)));
}

async function forgetReinstalledSession(): Promise<void> {
  const session = tokenPair(await keychain.get(SECURE_KEYS.session));
  if (session) {
    try {
      await oweLogout(session);
    } catch (error) {
      // A full Keychain: the server keeps the session until it ends, but this phone never
      // hands it back, so the clear below still runs.
      reportFailure("install_check", error);
    }
  }
  for (const key of CLEARED_ON_REINSTALL) await keychain.delete(key);
}

/** Set once this run's reinstall clear is done. */
let reinstallCleared = false;

async function checkInstall(): Promise<void> {
  // Required here so a test or a build without the native file system skips the check. A
  // `require`, not `import()`: in Expo Go's dev bundle the check behind `import()` never wrote
  // its marker (2026-11-27, Simulator).
  let files: typeof import("expo-file-system/legacy");
  let writeFileAtomically: typeof import("@/lib/durableFile").writeFileAtomically;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- loaded on first use, see above
    files = require("expo-file-system/legacy") as typeof import("expo-file-system/legacy");
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- loaded on first use, see above
    ({ writeFileAtomically } = require("@/lib/durableFile") as typeof import("@/lib/durableFile"));
  } catch (error) {
    reportFailure("install_check", error);
    return;
  }
  if (!files.documentDirectory) return;
  const marker = `${files.documentDirectory}${MARKER_FILE}`;
  const hasMarker = (await files.getInfoAsync(marker)).exists;
  const ran = (await keychain.get(RAN_KEY)) === RAN_VALUE;
  if (hasMarker && ran) return;
  if (!hasMarker && ran) {
    if (!reinstallCleared) await forgetReinstalledSession();
    reinstallCleared = true;
    // Before the marker: if it cannot be written, the next launch reads "no marker, no ran"
    // (rewrite, keep) and never clears the sign-in made after this clear.
    await keychain.delete(RAN_KEY);
  } else {
    await migrateItems();
  }
  await writeFileAtomically(marker, RAN_VALUE);
  await keychain.set(RAN_KEY, RAN_VALUE);
}

let installCheck: Promise<void> | null = null;
let failureReported = false;

/** The launch check, once a run; one that failed runs again on the next call. */
function installChecked(): Promise<void> {
  installCheck ??= checkInstall().catch(
    (error: unknown) => {
      installCheck = null;
      if (!failureReported) reportFailure("install_check", error);
      failureReported = true;
    },
  );
  return installCheck;
}

export async function secureGet(key: string): Promise<string | null> {
  await installChecked();
  return keychain.get(key);
}

export async function secureSet(key: string, value: string): Promise<void> {
  await installChecked();
  await keychain.set(key, value);
}

export async function secureDelete(key: string): Promise<void> {
  await installChecked();
  await keychain.delete(key);
}
