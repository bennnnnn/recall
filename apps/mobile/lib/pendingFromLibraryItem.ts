import type { AttachmentListItem } from "@/lib/api";
import type { AttachmentKind, PendingAttachment } from "@/lib/attachments";
import { resolveAttachmentUri } from "@/lib/attachmentUri";
import { ensureLocalAttachmentFile } from "@/lib/downloadChatAttachment";
import { galleryFileName } from "@/lib/gallery";

/** Build a composer attachment from a Library row (download images for the chip). */
export async function pendingFromLibraryItem(
  item: Pick<AttachmentListItem, "id" | "content_type" | "original_filename" | "download_url">,
  token: string | null,
): Promise<PendingAttachment> {
  const fileName = galleryFileName(item.content_type, item.original_filename);
  const kind: AttachmentKind = item.content_type.startsWith("image/") ? "image" : "file";
  const remoteUri = resolveAttachmentUri({
    attachmentId: item.id,
    path: item.download_url,
  });
  if (!remoteUri) {
    throw new Error("Could not attach");
  }
  const localUri =
    kind === "image"
      ? await ensureLocalAttachmentFile({ uri: remoteUri, token, fileName })
      : remoteUri;
  return {
    localUri,
    contentType: item.content_type,
    fileName,
    kind,
    existingAttachmentId: item.id,
  };
}
