import { Directory, File, Paths } from "expo-file-system";

import { AttachmentError } from "@/features/attachments/model/attachmentErrors";
import { MAX_ATTACHMENT_BYTES } from "@/features/attachments/model/attachmentLimits";
import { assetToPending, type PendingAttachment } from "@/features/attachments/model/attachments";
import { OPENED_FILE_DIRECTORY } from "@/lib/accountFiles";

/** What Android's module read beside the URI, off the JS thread: a content URI carries none of it. */
export type OpenedFileInfo = { name?: string; size?: number; type?: string };

/** The extension a type gives a name that has none (an Android provider's "1000123"). */
const EXTENSIONS: Readonly<Record<string, string>> = { "application/pdf": "pdf" };

function lastSegment(uri: string): string {
  const path = uri.split(/[?#]/)[0] ?? "";
  const segment = path.slice(path.lastIndexOf("/") + 1);
  try {
    return decodeURIComponent(segment);
  } catch (error) {
    // A malformed escape: the name as it was written.
    if (error instanceof URIError) return segment;
    throw error;
  }
}

/**
 * The name the composer shows and the upload carries: the other app's (Android), else
 * the file's own (iOS names its Inbox copy after the original). Never a path.
 */
export function openedFileName(uri: string, name: string | undefined, contentType: string): string {
  const given = (name?.trim() || lastSegment(uri)).replace(/[\\/]/g, "_").trim();
  const extension = EXTENSIONS[contentType];
  if (!given) return `file-${Date.now()}${extension ? `.${extension}` : ""}`;
  return extension && !/\.[a-z0-9]+$/i.test(given) ? `${given}.${extension}` : given;
}

/** A size, or 0 when it is unknown, so the copy is checked instead. */
function knownSize(size: number | undefined): number {
  return size !== undefined && Number.isSafeInteger(size) && size > 0 ? size : 0;
}

/**
 * The size and type before the copy. A `content:` URI's come from Android's module, which
 * asked the provider off the JS thread: expo-file-system's `exists` opens the stream, and its
 * `size` reads a provider that gives none to the end, both on the thread that asks. iOS's
 * file is a local one, asked here.
 */
function facts(source: File, uri: string, info: OpenedFileInfo): { size: number; type: string } {
  if (/^content:/i.test(uri)) return { size: knownSize(info.size), type: info.type ?? "" };
  try {
    if (!source.exists) throw new AttachmentError("unreadable");
    return { size: knownSize(source.size), type: source.type || "" };
  } catch (error) {
    throw error instanceof AttachmentError ? error : new AttachmentError("unreadable");
  }
}

/** A failure this file works around, by kind only: a file system error can carry the file's path. */
function warn(stage: string, error: unknown): void {
  console.warn("[openedFile]", { stage, error: error instanceof Error ? error.name : typeof error });
}

async function copyIntoCache(source: File, fileName: string): Promise<File> {
  const directory = new Directory(Paths.cache, OPENED_FILE_DIRECTORY);
  const extension = /\.([a-z0-9]+)$/i.exec(fileName)?.[1]?.toLowerCase();
  const unique = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const copy = new File(directory, `opened-${unique}${extension ? `.${extension}` : ""}`);
  try {
    directory.create({ idempotent: true, intermediates: true });
    await source.copy(copy);
    return copy;
  } catch (error) {
    // The other app took its permission back, or the file went: the toast says Recall could not open it.
    warn("copy", error);
    try {
      if (copy.exists) copy.delete();
    } catch (cleanupError) {
      // The cache directory is swept anyway (lib/accountFiles.ts).
      warn("delete_partial_copy", cleanupError);
    }
    throw new AttachmentError("unreadable");
  }
}

/**
 * A file another app opened in Recall, as a composer attachment: copied into the cache
 * (expo-file-system reads an Android content URI as well as a file, off the JS thread), then
 * prepared and checked as a pick is (`assetToPending`). One larger than the API takes is
 * refused before it is copied when its size is known, and after otherwise; a refused copy
 * is deleted.
 */
export async function copyOpenedDocument(uri: string, info: OpenedFileInfo = {}): Promise<PendingAttachment> {
  const source = new File(uri);
  const { size, type } = facts(source, uri, info);
  if (size > MAX_ATTACHMENT_BYTES) throw new AttachmentError("too_large");
  const fileName = openedFileName(uri, info.name, type);
  const copy = await copyIntoCache(source, fileName);
  return assetToPending({ uri: copy.uri, contentType: type, fileName });
}
