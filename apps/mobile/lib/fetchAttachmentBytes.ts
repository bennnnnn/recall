import { File } from "expo-file-system";
import { recallAttachmentPath } from "@/lib/attachmentUri";
import { attachmentSessionGuard } from "@/lib/attachmentSession";
import { requestRaw } from "@/lib/api/client";
import { arrayBufferToBase64 } from "@/lib/base64";

export async function fetchAttachmentBytes(
  uri: string,
  token: string | null,
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
  const response = path ? await requestRaw(path, token) : await fetch(uri);
  if (!response.ok) throw new Error("Could not load attachment.");
  const bytes = await response.arrayBuffer();
  requireCurrent();
  return bytes;
}

export async function fetchAttachmentBase64(
  uri: string,
  token: string | null,
): Promise<string> {
  const buffer = await fetchAttachmentBytes(uri, token);
  return arrayBufferToBase64(buffer);
}
