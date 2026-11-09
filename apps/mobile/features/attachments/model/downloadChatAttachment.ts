import { copyAsync, deleteAsync, getInfoAsync, moveAsync } from "expo-file-system/legacy";
import { randomUUID } from "expo-crypto";
import * as MediaLibrary from "expo-media-library";

import { downloadAttachmentFile } from "@/features/attachments/model/fetchAttachmentBytes";
import { getSessionGeneration, SessionChangedError } from "@/lib/auth";
import { recallAttachmentPath } from "@/features/attachments/model/attachmentUri";
import { attachmentSessionGuard } from "@/features/attachments/model/attachmentSession";
import {
  attachmentFilePath,
  listAttachmentFiles,
  listRecallAttachmentFiles,
  partialFilePath,
  safeFileName,
  sweepAttachmentFiles,
} from "@/features/attachments/model/attachmentFileStore";
import { contentTypeForFileName } from "@/features/attachments/model/gallery";
import { newShareFile } from "@/lib/accountFiles";
import { shareLocalFile, shareOneAtATime } from "@/lib/share/file";

/** One native download, shared by every screen that asked for the same URL. */
type Download = {
  uri: string;
  promise: Promise<string>;
  /** Callers still waiting; the last one to leave cancels the transfer. */
  waiters: number;
  controller: AbortController;
};

const localFileCache = new Map<string, string>();
const downloadsInFlight = new Map<string, Download>();
/** Files this run wrote, reused or is writing → their URL. The sweep and sign-out spare them. */
const cachedFiles = new Map<string, string>();
const downloadRevisions = new Map<string, number>();
/** Retry asked for fresh bytes: the copy on disk may be the unreadable one. */
const refetch = new Set<string>();
let cacheGeneration: number | null = null;
let cacheRevision = 0;
let swept = false;

function scopeCacheToSession(): void {
  if (cacheGeneration === getSessionGeneration()) return;
  localFileCache.clear();
  downloadsInFlight.clear();
  downloadRevisions.clear();
  cacheGeneration = getSessionGeneration();
  cacheRevision++;
}

/** Once per run, before the first download: earlier runs' copies are bounded here. */
function sweepOnce(): void {
  if (swept) return;
  swept = true;
  void sweepAttachmentFiles((path) => cachedFiles.has(path)).catch(() => undefined);
}

function abortError(): Error {
  const error = new Error("Download canceled");
  error.name = "AbortError";
  return error;
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
  refetch.add(uri);
}

/** A successful Library delete also removes its full-size and thumbnail files. */
export async function removeCachedAttachmentFiles(attachmentId: string): Promise<void> {
  scopeCacheToSession();
  const isThisFile = (uri: string) =>
    recallAttachmentPath(uri)?.split("?")[0] === `/attachments/${attachmentId}/file`;
  const remembered = [...cachedFiles].filter(([, uri]) => isThisFile(uri)).map(([path]) => path);
  for (const uri of new Set([...localFileCache.keys(), ...downloadsInFlight.keys(), ...cachedFiles.values()])) {
    if (isThisFile(uri)) invalidateCachedAttachmentFile(uri);
  }
  const onDisk = await listRecallAttachmentFiles(attachmentId).catch(() => [] as string[]);
  await Promise.allSettled([...new Set([...remembered, ...onDisk])].map(async (path) => {
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
  refetch.clear();
  cacheGeneration = getSessionGeneration();
  cacheRevision++;
}

/** Logout also removes this helper's att-* files left by earlier app runs. */
export async function clearLocalAttachmentFileCache(): Promise<void> {
  const remembered = new Set(cachedFiles.keys());
  resetLocalAttachmentFileCache();
  const paths = new Set([...remembered, ...(await listAttachmentFiles())]);
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

async function hasContent(path: string): Promise<boolean> {
  const info = await getInfoAsync(path).catch(() => null);
  return Boolean(info?.exists && !info.isDirectory && info.size > 0);
}

function remember(uri: string, path: string): string {
  localFileCache.set(uri, path);
  cachedFiles.set(path, uri);
  return path;
}

function startDownload(uri: string, token: string | null, fileName: string): Download {
  const requireCurrent = attachmentSessionGuard(token);
  const revision = cacheRevision;
  const uriRevision = downloadRevisions.get(uri) ?? 0;
  const requireCurrentDownload = () => {
    requireCurrent();
    if (revision !== cacheRevision) throw new SessionChangedError();
    if (uriRevision !== (downloadRevisions.get(uri) ?? 0)) {
      throw new Error("Attachment changed. Please try again.");
    }
  };
  const controller = new AbortController();
  const promise = (async () => {
    const cached = localFileCache.get(uri);
    if (cached) {
      const exists = await hasContent(cached);
      requireCurrentDownload();
      if (exists) return cached;
      localFileCache.delete(uri);
    }
    const dest = await attachmentFilePath(uri, fileName);
    if (!refetch.has(uri) && await hasContent(dest)) {
      requireCurrentDownload();
      return remember(uri, dest);
    }
    const partial = partialFilePath(dest, randomUUID().slice(0, 8));
    cachedFiles.set(partial, uri);
    let placed = false;
    try {
      await downloadAttachmentFile(uri, partial, token, controller.signal);
      requireCurrentDownload();
      await deleteAsync(dest, { idempotent: true });
      await moveAsync({ from: partial, to: dest });
      placed = true;
      requireCurrentDownload();
      refetch.delete(uri);
      return remember(uri, dest);
    } catch (error) {
      await deleteAsync(placed ? dest : partial, { idempotent: true }).catch(() => undefined);
      throw error;
    } finally {
      cachedFiles.delete(partial);
    }
  })();
  return { uri, promise, waiters: 0, controller };
}

/** Wait for a shared download; an aborted caller stops waiting, and the last one stops the transfer. */
function joinDownload(download: Download, signal?: AbortSignal): Promise<string> {
  // A caller without a signal (share, save) always wants the file, so it never leaves.
  download.waiters++;
  if (!signal) return download.promise;
  if (signal.aborted) {
    download.waiters--;
    return Promise.reject(abortError());
  }
  return new Promise<string>((resolve, reject) => {
    const leave = () => {
      download.waiters--;
      if (download.waiters === 0) {
        download.controller.abort();
        // The next viewer starts a new transfer instead of joining the canceled one.
        if (downloadsInFlight.get(download.uri) === download) downloadsInFlight.delete(download.uri);
      }
      reject(abortError());
    };
    signal.addEventListener("abort", leave, { once: true });
    download.promise.then(resolve, reject).finally(() => signal.removeEventListener("abort", leave));
  });
}

/**
 * The attachment as a local file, downloaded natively once and kept under a
 * name derived from its URL, so later views, shares and app runs reuse it.
 */
export async function ensureLocalAttachmentFile(options: {
  uri: string;
  token?: string | null;
  fileName?: string;
  /** Stop waiting (a closed viewer); the transfer stops when nobody else waits. */
  signal?: AbortSignal;
}): Promise<string> {
  const { uri, token = null, fileName = "attachment.jpg", signal } = options;
  const requireCurrent = attachmentSessionGuard(token);
  if (uri.startsWith("file://") || uri.startsWith("content://")) return uri;
  if (!uri.startsWith("http://") && !uri.startsWith("https://")) {
    throw new Error("Could not open this attachment.");
  }
  scopeCacheToSession();
  sweepOnce();
  let download = downloadsInFlight.get(uri);
  if (!download) {
    const started = startDownload(uri, token, fileName);
    download = started;
    downloadsInFlight.set(uri, started);
    void started.promise.catch(() => undefined).finally(() => {
      if (downloadsInFlight.get(uri) === started) downloadsInFlight.delete(uri);
    });
  }
  const local = await joinDownload(download, signal);
  requireCurrent();
  return local;
}

/** Open the system share sheet for a local or remote attachment. */
export async function shareChatAttachment(options: {
  uri: string;
  token?: string | null;
  fileName?: string;
  /** MIME type for Android's share targets; guessed from the file name when missing. */
  contentType?: string | null;
}): Promise<void> {
  const { uri, token = null, fileName = "attachment.jpg", contentType } = options;
  const requireCurrent = attachmentSessionGuard(token);
  const safeName = safeFileName(fileName, `recall-${Date.now()}.jpg`);
  const localUri = await ensureLocalAttachmentFile({ uri, token, fileName: safeName });
  requireCurrent();

  const mimeType = contentType?.split(";")[0]?.trim() || contentTypeForFileName(safeName);
  const name = sharedFileName(fileName) ?? safeName;
  const shared = await sharedCopy(localUri, name);
  try {
    requireCurrent();
  } catch (error) {
    // Signed out during the copy: the copy is that account's file.
    if (shared.folder) await discardShareFolder(shared.folder);
    throw error;
  }
  await shareLocalFile(shared.uri, { title: name, mimeType });
}

/** A file name holds 255 bytes; a shared one keeps to this many, in UTF-8. */
const SHARED_NAME_MAX_BYTES = 200;

function utf8Length(char: string): number {
  const code = char.codePointAt(0) ?? 0;
  return code < 0x80 ? 1 : code < 0x800 ? 2 : code < 0x10000 ? 3 : 4;
}

/**
 * The name a file goes out under: its own, with only what a file name cannot hold replaced.
 * A long one is cut before its extension, by whole characters, so it keeps its type and fits
 * (124 Amharic letters are 364 bytes). `null` when nothing of it is left.
 */
function sharedFileName(fileName: string): string | null {
  const cleaned = Array.from(fileName, (char) => (char.charCodeAt(0) < 32 || '\\/:*?"<>|'.includes(char) ? "_" : char))
    .join("")
    .trim();
  if (!cleaned || /^\.+$/.test(cleaned)) return null;
  const extension = cleaned.match(/.\.[a-zA-Z0-9]{1,12}$/)?.[0].slice(1) ?? "";
  let room = SHARED_NAME_MAX_BYTES - extension.length;
  const stem: string[] = [];
  for (const char of cleaned.slice(0, cleaned.length - extension.length)) {
    room -= utf8Length(char);
    if (room < 0) break;
    stem.push(char);
  }
  return `${stem.join("")}${extension}`;
}

/** The shared copy, and the folder it is in; none when the cached file goes as it is. */
type SharedCopy = { uri: string; folder: string | null };

/**
 * The cached download under its own name ("report.xlsx"), in a folder of its own: shared as
 * the cache names it, the app it went to showed "att-6cc2e003043008e6-e3b0c442-report.xlsx"
 * (S23, 2026-11-07). A copy that cannot be made shares the cached file as before.
 */
async function sharedCopy(localUri: string, name: string): Promise<SharedCopy> {
  if (!localUri.startsWith("file://")) return { uri: localUri, folder: null };
  let folder: string | null = null;
  try {
    const target = await newShareFile(name);
    folder = target.folder;
    await copyAsync({ from: localUri, to: target.file });
    return { uri: target.file, folder };
  } catch (error) {
    console.warn("[share] named copy failed; sharing the cached file", error instanceof Error ? error.name : typeof error);
    if (folder) await discardShareFolder(folder);
    return { uri: localUri, folder: null };
  }
}

async function discardShareFolder(folder: string): Promise<void> {
  await deleteAsync(folder, { idempotent: true }).catch((error: unknown) =>
    console.warn("[share] could not delete a share folder", error instanceof Error ? error.name : typeof error));
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
      await MediaLibrary.Asset.create(localUri);
      requireCurrent();
      return "saved";
    } catch {
      requireCurrent();
    }
  }
  // A share sheet, like every other: one at a time.
  await shareOneAtATime(() => shareChatAttachment({ uri: localUri, fileName }));
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
