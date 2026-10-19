import { File } from "expo-file-system";
import { recallAttachmentPath } from "@/features/attachments/model/attachmentUri";
import { attachmentSessionGuard } from "@/features/attachments/model/attachmentSession";
import { authorizeNativeTransfer, requestRaw } from "@/lib/api/client";

/** Read an attachment into memory; for small files the screen shows as text. */
export async function fetchAttachmentBytes(
  uri: string,
  token: string | null,
  signal?: AbortSignal,
): Promise<ArrayBuffer> {
  const requireCurrent = attachmentSessionGuard(token);
  if (uri.startsWith("file://") || uri.startsWith("content://")) {
    const bytes = await new File(uri).arrayBuffer();
    requireCurrent();
    return bytes;
  }
  const path = recallAttachmentPath(uri);
  // External and local file URLs never receive Recall credentials. API
  // downloads share the same session fences and refresh policy as JSON/SSE.
  const response = path ? await requestRaw(path, token, { signal }) : await fetch(uri, { signal });
  if (!response.ok) throw new Error("Could not load attachment.");
  const bytes = await response.arrayBuffer();
  requireCurrent();
  return bytes;
}

const HTTP_STATUS = /status:? (\d{3})|HTTP (\d{3})/;

/** The native module reports a refused download only in its message. */
function failedStatus(error: unknown): number | null {
  const match = error instanceof Error ? HTTP_STATUS.exec(error.message) : null;
  return match ? Number(match[1] ?? match[2]) : null;
}

/**
 * Stream an attachment straight to `dest` natively: the bytes never cross
 * into JavaScript. Recall URLs get the Bearer header (refreshed like fetch);
 * any other URL is downloaded without credentials.
 */
export async function downloadAttachmentFile(
  uri: string,
  dest: string,
  token: string | null,
  signal?: AbortSignal,
): Promise<void> {
  const send = async (headers: Record<string, string>): Promise<number> => {
    try {
      await File.downloadFileAsync(uri, new File(dest), { headers, idempotent: true, signal });
      return 200;
    } catch (error) {
      const status = failedStatus(error);
      if (status === null) throw error;
      return status;
    }
  };
  const status = recallAttachmentPath(uri) ? await authorizeNativeTransfer(token, send) : await send({});
  if (status !== 200) throw new Error("Could not load attachment.");
}
