import { notifyUnauthorized, refreshAccessToken } from "@/lib/api/client";
import { arrayBufferToBase64 } from "@/lib/base64";

function attachmentAuthHeaders(
  uri: string,
  token: string | null,
): Record<string, string> {
  if (token && uri.includes("/attachments/")) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

export async function fetchAttachmentBytes(
  uri: string,
  token: string | null,
): Promise<ArrayBuffer> {
  const response = await fetch(uri, { headers: attachmentAuthHeaders(uri, token) });
  if (response.status === 401 && token && uri.includes("/attachments/")) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      const retry = await fetch(uri, { headers: attachmentAuthHeaders(uri, refreshed) });
      if (retry.ok) return retry.arrayBuffer();
    } else {
      notifyUnauthorized();
    }
  }
  if (!response.ok) {
    throw new Error("Could not load attachment.");
  }
  return response.arrayBuffer();
}

export async function fetchAttachmentBase64(
  uri: string,
  token: string | null,
): Promise<string> {
  const buffer = await fetchAttachmentBytes(uri, token);
  return arrayBufferToBase64(buffer);
}
