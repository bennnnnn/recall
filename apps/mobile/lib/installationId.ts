/**
 * Stable per-install id for push token re-bind checks.
 *
 * Expo removed `Constants.installationId`; we generate one and keep it in the secure store,
 * this phone only (`lib/secureStore.ts`): an id in the documents directory travelled to a new
 * phone in a backup, and the two phones then deleted each other's push token. A reinstall
 * clears it there, so a reinstalled app gets a new one.
 *
 * Earlier versions kept it in a documents file. Its first read here moves that id into the
 * secure store, so an upgrade keeps its id. Where the secure store cannot be used (an
 * entitlement-less simulator build) the file's id is still read, and none is made.
 */

import * as Crypto from "expo-crypto";
import {
  deleteAsync,
  documentDirectory,
  getInfoAsync,
  readAsStringAsync,
} from "expo-file-system/legacy";

import { SECURE_KEYS, secureGet, secureSet } from "@/lib/secureStore";
import { reportFailure } from "@/lib/sentry";

const LEGACY_FILE_NAME = "recall.installation-id.txt";

function legacyPath(): string | null {
  return documentDirectory ? `${documentDirectory}${LEGACY_FILE_NAME}` : null;
}

async function readLegacyId(path: string | null): Promise<string | null> {
  if (!path) return null;
  try {
    if (!(await getInfoAsync(path)).exists) return null;
    return (await readAsStringAsync(path)).trim() || null;
  } catch {
    return null;
  }
}

async function readOrCreateId(): Promise<string | null> {
  const path = legacyPath();
  let stored: string | null;
  try {
    stored = await secureGet(SECURE_KEYS.installationId);
  } catch (error) {
    reportFailure("installation_id", error);
    return readLegacyId(path);
  }
  if (stored) return stored;
  const legacy = await readLegacyId(path);
  const next = legacy ?? Crypto.randomUUID();
  try {
    await secureSet(SECURE_KEYS.installationId, next);
  } catch (error) {
    reportFailure("installation_id", error);
    return legacy;
  }
  if (legacy && path) await deleteAsync(path, { idempotent: true }).catch(() => {});
  return next;
}

/** The read that is running: callers at once (push registration, an analytics flush) share
 * it, so a first launch never moves the old id and makes a new one over it. */
let reading: Promise<string | null> | null = null;

export function getInstallationId(): Promise<string | null> {
  reading ??= readOrCreateId().finally(() => {
    reading = null;
  });
  return reading;
}
