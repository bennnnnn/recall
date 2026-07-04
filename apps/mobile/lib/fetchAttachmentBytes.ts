import { arrayBufferToBase64 } from "@/lib/base64";

export async function fetchAttachmentBytes(
  uri: string,
  token: string | null,
): Promise<ArrayBuffer> {
  const headers: Record<string, string> = {};
  if (token && uri.includes("/attachments/")) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(uri, { headers });
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
