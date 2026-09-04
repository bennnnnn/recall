import { apiUrl, requestRaw } from "@/lib/api/client";
import { arrayBufferToBase64 } from "@/lib/base64";

function recallAttachmentPath(uri: string): string | null {
  try {
    const base = new URL(apiUrl("/"));
    const url = new URL(uri);
    const basePath = base.pathname.replace(/\/$/, "");
    if (url.origin !== base.origin || url.username || url.password ||
      !url.pathname.startsWith(`${basePath}/attachments/`)) return null;
    return `${url.pathname.slice(basePath.length)}${url.search}`;
  } catch {
    return null;
  }
}

export async function fetchAttachmentBytes(
  uri: string,
  token: string | null,
): Promise<ArrayBuffer> {
  const path = recallAttachmentPath(uri);
  // External and local file URLs never receive Recall credentials. API
  // downloads share the same session fences and refresh policy as JSON/SSE.
  const response = path ? await requestRaw(path, token) : await fetch(uri);
  if (!response.ok) throw new Error("Could not load attachment.");
  return response.arrayBuffer();
}

export async function fetchAttachmentBase64(
  uri: string,
  token: string | null,
): Promise<string> {
  const buffer = await fetchAttachmentBytes(uri, token);
  return arrayBufferToBase64(buffer);
}
