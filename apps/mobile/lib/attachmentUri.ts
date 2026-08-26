import { getApiUrl } from "@/lib/config";
import { attachmentIdFromRef } from "@/lib/attachmentRef";

export { attachmentIdFromRef };

export function resolveAttachmentUri(options: {
  attachmentId?: string | null;
  localUri?: string | null;
  path?: string | null;
  width?: number | null;
}): string | null {
  if (options.localUri) return options.localUri;
  let uri: string | null = null;
  if (options.attachmentId) {
    uri = `${getApiUrl()}/attachments/${options.attachmentId}/file`;
  } else {
    const path = options.path?.trim();
    if (!path) return null;
    if (path.startsWith("http://") || path.startsWith("https://")) uri = path;
    else if (path.startsWith("/attachments/")) uri = `${getApiUrl()}${path}`;
  }
  if (!uri) return null;
  const width = options.width;
  if (width && width > 0) {
    const sep = uri.includes("?") ? "&" : "?";
    return `${uri}${sep}w=${Math.round(width)}`;
  }
  return uri;
}
