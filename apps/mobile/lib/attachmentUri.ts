import { getApiUrl } from "@/lib/config";
import { attachmentIdFromRef } from "@/lib/attachmentRef";

export { attachmentIdFromRef };

export function resolveAttachmentUri(options: {
  attachmentId?: string | null;
  localUri?: string | null;
  path?: string | null;
}): string | null {
  if (options.localUri) return options.localUri;
  if (options.attachmentId) return `${getApiUrl()}/attachments/${options.attachmentId}/file`;
  const path = options.path?.trim();
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  if (path.startsWith("/attachments/")) return `${getApiUrl()}${path}`;
  return null;
}
