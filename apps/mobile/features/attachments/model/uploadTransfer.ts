/**
 * A file's PUT to its presigned storage URL, by the system's own upload (expo-file-system's
 * `File.upload`, in Expo Go and native builds alike since SDK 58): it reads the file
 * itself, says how far it has got, and stops on Cancel.
 *
 * It ran as one `fetch` of the whole file under a 120 s total timer, which a 10 MB PDF
 * could not beat below about 0.7 Mbps. An upload now fails only when it stalls: no
 * progress for `UPLOAD_STALL_MS`, however long the whole file takes.
 */
import { File, UploadType } from "expo-file-system";

import type { AttachmentTransfer, UploadTarget } from "@/features/attachments/api";
import { AttachmentError, UploadCancelledError } from "@/features/attachments/model/attachmentErrors";
import { getSessionGeneration, SessionChangedError } from "@/lib/auth";

/** No byte sent (or no answer after the last one) for this long: the upload has stalled. */
const UPLOAD_STALL_MS = 30_000;

type StorageUpload = AttachmentTransfer & {
  url: string;
  localUri: string;
  headers: Record<string, string>;
  stallMs?: number;
};

/** PUTs the file; resolves with the storage's HTTP status. */
async function putFileToStorage({
  url,
  localUri,
  headers,
  onProgress,
  signal,
  stallMs = UPLOAD_STALL_MS,
}: StorageUpload): Promise<number> {
  if (signal?.aborted) throw new UploadCancelledError();
  const stop = new AbortController();
  let stalled = false;
  let watchdog: ReturnType<typeof setTimeout> | undefined;
  const rearm = () => {
    clearTimeout(watchdog);
    watchdog = setTimeout(() => {
      stalled = true;
      stop.abort();
    }, stallMs);
  };
  const onCancel = () => stop.abort();
  signal?.addEventListener("abort", onCancel, { once: true });
  rearm();
  try {
    const result = await new File(localUri).upload(url, {
      httpMethod: "PUT",
      uploadType: UploadType.BINARY_CONTENT,
      headers,
      signal: stop.signal,
      onProgress: ({ bytesSent, totalBytes }) => {
        rearm();
        if (totalBytes > 0) onProgress?.(bytesSent / totalBytes);
      },
    });
    return result.status;
  } catch (error) {
    if (signal?.aborted) throw new UploadCancelledError();
    if (stalled) throw new AttachmentError("upload_failed");
    throw error;
  } finally {
    clearTimeout(watchdog);
    signal?.removeEventListener("abort", onCancel);
  }
}

/** The file at `localUri` to its presigned storage URL, never with Recall's credentials. */
export async function uploadAttachmentFile(
  target: UploadTarget,
  contentType: string,
  localUri: string,
  transfer: AttachmentTransfer = {},
): Promise<void> {
  const url = new URL(target.upload_url);
  if (url.protocol !== "https:" || url.username || url.password) {
    throw new AttachmentError("upload_failed");
  }
  const generation = getSessionGeneration();
  const status = await putFileToStorage({
    url: url.toString(),
    localUri,
    headers: { "Content-Type": contentType, ...target.headers },
    ...transfer,
  });
  if (generation !== getSessionGeneration()) throw new SessionChangedError();
  if (status < 200 || status >= 300) throw new AttachmentError("upload_failed");
}
