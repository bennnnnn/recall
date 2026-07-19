import {
  cacheDirectory,
  downloadAsync,
} from "expo-file-system/legacy";
import * as MediaLibrary from "expo-media-library";
import { Platform, Share } from "react-native";

function safeFileName(name: string, fallback: string): string {
  const cleaned = name.replace(/[^\w.-]+/g, "_").replace(/^_+|_+$/g, "");
  return cleaned || fallback;
}

function cacheKeyForUri(uri: string): string {
  return uri.replace(/[^\w.-]+/g, "_").slice(-80);
}

/** In-memory map of remote/attachment URI → local file:// cache path. */
const localFileCache = new Map<string, string>();

export function getCachedAttachmentFile(uri: string): string | null {
  return localFileCache.get(uri) ?? null;
}

/**
 * Resolve a chat attachment to a local file:// URI.
 * Prefers ``downloadAsync`` (with auth headers) over ``createDownloadResumable``,
 * which throws ERR_FILESYSTEM_CANNOT_DOWNLOAD on authenticated attachment URLs.
 */
export async function ensureLocalAttachmentFile(options: {
  uri: string;
  token?: string | null;
  fileName?: string;
}): Promise<string> {
  const { uri, token = null, fileName = "attachment.jpg" } = options;
  if (uri.startsWith("file://") || uri.startsWith("content://")) {
    return uri;
  }

  const cached = localFileCache.get(uri);
  if (cached) return cached;

  const dir = cacheDirectory;
  if (!dir) throw new Error("Storage unavailable.");

  const safeName = safeFileName(fileName, `recall-${Date.now()}.jpg`);
  const dest = `${dir}att-${cacheKeyForUri(uri)}-${safeName}`;

  if (!uri.startsWith("http://") && !uri.startsWith("https://")) {
    return uri;
  }

  const headers =
    token && uri.includes("/attachments/")
      ? { Authorization: `Bearer ${token}` }
      : undefined;

  const result = await downloadAsync(uri, dest, { headers });
  if (!result?.uri) throw new Error("Download failed.");
  localFileCache.set(uri, result.uri);
  return result.uri;
}

/** Open the system share sheet for a local or remote attachment. */
export async function shareChatAttachment(options: {
  uri: string;
  token?: string | null;
  fileName?: string;
}): Promise<void> {
  const { uri, token = null, fileName = "attachment.jpg" } = options;
  const safeName = safeFileName(fileName, `recall-${Date.now()}.jpg`);
  const localUri = await ensureLocalAttachmentFile({ uri, token, fileName: safeName });

  await Share.share(
    Platform.OS === "ios"
      ? { url: localUri, title: safeName }
      : { message: localUri, title: safeName, url: localUri },
  );
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
  const localUri = await ensureLocalAttachmentFile({ uri, token, fileName });

  try {
    const permission = await MediaLibrary.requestPermissionsAsync(true);
    if (!permission.granted) {
      await shareChatAttachment({ uri: localUri, fileName });
      return "shared";
    }
    await MediaLibrary.saveToLibraryAsync(localUri);
    return "saved";
  } catch {
    // Native module missing until a rebuild, or Photos save failed — share sheet.
    await shareChatAttachment({ uri: localUri, fileName });
    return "shared";
  }
}

/** Share sheet export (PDF / generic attachments). */
export async function downloadChatAttachment(options: {
  uri: string;
  token?: string | null;
  fileName?: string;
}): Promise<void> {
  await shareChatAttachment(options);
}
