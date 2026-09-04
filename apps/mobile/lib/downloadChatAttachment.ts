import {
  cacheDirectory,
  EncodingType,
  getInfoAsync,
  readDirectoryAsync,
  deleteAsync,
  writeAsStringAsync,
} from "expo-file-system/legacy";
import { randomUUID } from "expo-crypto";
import * as MediaLibrary from "expo-media-library";
import { Platform, Share } from "react-native";

import { fetchAttachmentBase64 } from "@/lib/fetchAttachmentBytes";
import { getSessionGeneration, SessionChangedError } from "@/lib/auth";
import { recallAttachmentPath } from "@/lib/attachmentUri";
import { attachmentSessionGuard } from "@/lib/attachmentSession";
import { isShareCancelled } from "@/lib/exportPdf";

function safeFileName(name: string, fallback: string): string {
  const cleaned = name.replace(/[^\w.-]+/g, "_").replace(/^_+|_+$/g, "");
  if (!cleaned) return fallback;
  const extension = cleaned.match(/\.[a-zA-Z0-9]{1,12}$/)?.[0] ?? "";
  const stem = extension ? cleaned.slice(0, -extension.length) : cleaned;
  return `${stem.slice(0, 160)}${extension}`;
}

const localFileCache = new Map<string, string>();
const downloadsInFlight = new Map<string, Promise<string>>();
const cachedFiles = new Map<string, string>();
const downloadRevisions = new Map<string, number>();
let cacheGeneration: number | null = null;
let cacheRevision = 0;

function scopeCacheToSession(): void {
  if (cacheGeneration === getSessionGeneration()) return;
  localFileCache.clear();
  downloadsInFlight.clear();
  downloadRevisions.clear();
  cacheGeneration = getSessionGeneration();
  cacheRevision++;
}

export function getCachedAttachmentFile(uri: string): string | null {
  scopeCacheToSession();
  return localFileCache.get(uri) ?? null;
}

/** Force Retry to fetch fresh bytes instead of reusing an unreadable cache file. */
export function invalidateCachedAttachmentFile(uri: string): void {
  localFileCache.delete(uri);
  downloadsInFlight.delete(uri);
  downloadRevisions.set(uri, (downloadRevisions.get(uri) ?? 0) + 1);
}

/** A successful Library delete also removes its full-size and thumbnail files. */
export async function removeCachedAttachmentFiles(attachmentId: string): Promise<void> {
  scopeCacheToSession();
  const paths = [...cachedFiles].filter(([, uri]) =>
    recallAttachmentPath(uri)?.split("?")[0] === `/attachments/${attachmentId}/file`,
  ).map(([path]) => path);
  for (const uri of new Set([...localFileCache.keys(), ...downloadsInFlight.keys(), ...cachedFiles.values()])) {
    if (recallAttachmentPath(uri)?.split("?")[0] !== `/attachments/${attachmentId}/file`) continue;
    invalidateCachedAttachmentFile(uri);
  }
  await Promise.allSettled(paths.map(async (path) => {
    await deleteAsync(path, { idempotent: true });
    cachedFiles.delete(path);
  }));
}

/** Test helper — drop cache references between cases. */
export function resetLocalAttachmentFileCache(): void {
  localFileCache.clear();
  downloadsInFlight.clear();
  downloadRevisions.clear();
  cachedFiles.clear();
  cacheGeneration = getSessionGeneration();
  cacheRevision++;
}

/** Logout also removes this helper's att-* files left by earlier app runs. */
export async function clearLocalAttachmentFileCache(): Promise<void> {
  const remembered = new Set(cachedFiles.keys());
  resetLocalAttachmentFileCache();
  const paths = new Set(remembered);
  if (cacheDirectory) {
    const names = await readDirectoryAsync(cacheDirectory).catch(() => []);
    for (const name of names) {
      // Only this helper writes att-* cache files. Accept basenames only, and
      // keep directories and every other cache owner outside this cleanup.
      if (/^att-[\w.-]+$/.test(name)) paths.add(`${cacheDirectory}${name}`);
    }
  }
  await Promise.allSettled([...paths].map(async (path) => {
    // A new download may have started while directory enumeration was pending.
    if (cachedFiles.has(path)) return;
    if (!remembered.has(path)) {
      const info = await getInfoAsync(path);
      if (!info.exists || info.isDirectory) return;
    }
    await deleteAsync(path, { idempotent: true });
  }));
}

/** Fetch authenticated bytes once, checking session identity before saving them. */
export async function ensureLocalAttachmentFile(options: {
  uri: string;
  token?: string | null;
  fileName?: string;
}): Promise<string> {
  const { uri, token = null, fileName = "attachment.jpg" } = options;
  const requireCurrent = attachmentSessionGuard(token);
  if (uri.startsWith("file://") || uri.startsWith("content://")) return uri;
  if (!uri.startsWith("http://") && !uri.startsWith("https://")) {
    throw new Error("Could not open this attachment.");
  }
  scopeCacheToSession();
  const revision = cacheRevision;
  const uriRevision = downloadRevisions.get(uri) ?? 0;
  const requireCurrentDownload = () => {
    requireCurrent();
    if (revision !== cacheRevision) throw new SessionChangedError();
    if (uriRevision !== (downloadRevisions.get(uri) ?? 0)) {
      throw new Error("Attachment changed. Please try again.");
    }
  };
  const inFlight = downloadsInFlight.get(uri);
  if (inFlight) return inFlight;
  const download = (async () => {
    const cached = localFileCache.get(uri);
    if (cached) {
      const info = await getInfoAsync(cached);
      requireCurrentDownload();
      if (info.exists) return cached;
      localFileCache.delete(uri);
    }
    const dir = cacheDirectory;
    if (!dir) throw new Error("Storage unavailable.");
    const safeName = safeFileName(fileName, "attachment.jpg");
    // A unique filename avoids both URL-tail collisions and overwrites while
    // another request still has the previous cache file open.
    const dest = `${dir}att-${randomUUID()}-${safeName}`;
    cachedFiles.set(dest, uri);
    try {
      const base64 = await fetchAttachmentBase64(uri, token);
      requireCurrentDownload();
      await writeAsStringAsync(dest, base64, { encoding: EncodingType.Base64 });
      requireCurrentDownload();
      localFileCache.set(uri, dest);
      return dest;
    } catch (error) {
      await deleteAsync(dest, { idempotent: true }).catch(() => {});
      cachedFiles.delete(dest);
      throw error;
    }
  })();
  downloadsInFlight.set(uri, download);
  try {
    return await download;
  } finally {
    if (downloadsInFlight.get(uri) === download) downloadsInFlight.delete(uri);
  }
}

/** Open the system share sheet for a local or remote attachment. */
export async function shareChatAttachment(options: {
  uri: string;
  token?: string | null;
  fileName?: string;
}): Promise<void> {
  const { uri, token = null, fileName = "attachment.jpg" } = options;
  const requireCurrent = attachmentSessionGuard(token);
  const safeName = safeFileName(fileName, `recall-${Date.now()}.jpg`);
  const localUri = await ensureLocalAttachmentFile({ uri, token, fileName: safeName });
  requireCurrent();

  try {
    await Share.share(
      Platform.OS === "ios"
        ? { url: localUri, title: safeName }
        : { message: localUri, title: safeName, url: localUri },
    );
  } catch (error) {
    if (isShareCancelled(error)) return;
    throw error;
  }
}

/**
 * Save an image to the device photo library. Falls back to the share sheet
 * when the library permission is denied (user can still Save Image there).
 */
export async function saveChatAttachmentToLibrary(options: {
  uri: string;
  token?: string | null;
  fileName?: string;
}): Promise<"saved" | "shared"> {
  const { uri, token = null, fileName = "image.jpg" } = options;
  const requireCurrent = attachmentSessionGuard(token);
  const localUri = await ensureLocalAttachmentFile({ uri, token, fileName });
  requireCurrent();

  let granted = false;
  try {
    granted = (await MediaLibrary.requestPermissionsAsync(true)).granted;
  } catch {
    // Missing Photos support still allows exporting through the share sheet.
  }
  requireCurrent();
  if (granted) {
    try {
      await MediaLibrary.saveToLibraryAsync(localUri);
      requireCurrent();
      return "saved";
    } catch {
      requireCurrent();
    }
  }
  await shareChatAttachment({ uri: localUri, fileName });
  return "shared";
}

/** Share sheet export (PDF / generic attachments). */
export async function downloadChatAttachment(options: {
  uri: string;
  token?: string | null;
  fileName?: string;
}): Promise<void> {
  await shareChatAttachment(options);
}
