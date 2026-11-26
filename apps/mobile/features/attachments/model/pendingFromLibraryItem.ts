import type { AttachmentListItem } from "@/lib/api";
import type { AttachmentKind, PendingAttachment } from "@/features/attachments/model/attachments";
import { resolveAttachmentUri } from "@/features/attachments/model/attachmentUri";
import { ensureLocalAttachmentFile } from "@/features/attachments/model/downloadChatAttachment";
import { attachmentSessionGuard } from "@/features/attachments/model/attachmentSession";
import { galleryFileName } from "@/features/attachments/model/gallery";
import { pastedTextPreview } from "@/features/attachments/model/pastedText";
import { charCount } from "@/lib/charCount";
import { File } from "expo-file-system";

/** Retain local bytes so a restored Library attachment can be uploaded again. */
export async function pendingFromLibraryItem(
  item: Pick<AttachmentListItem, "id" | "content_type" | "original_filename" | "download_url"> &
    Partial<Pick<AttachmentListItem, "source" | "pasted">>,
  token: string | null,
): Promise<PendingAttachment> {
  const requireCurrent = attachmentSessionGuard(token);
  const fileName = galleryFileName(item.content_type, item.original_filename, item.source);
  const kind: AttachmentKind = item.content_type.startsWith("image/") ? "image" : "file";
  const remoteUri = resolveAttachmentUri({
    attachmentId: item.id,
    path: item.download_url,
  });
  if (!remoteUri) {
    throw new Error("Could not attach");
  }
  const localUri = await ensureLocalAttachmentFile({ uri: remoteUri, token, fileName });
  requireCurrent();
  // A paste sent again is a paste on the phone too (its chip, no "Summarize this file."), as
  // the API's copy of the row keeps it one.
  const text = item.pasted ? await new File(localUri).text() : null;
  requireCurrent();
  return {
    localUri,
    contentType: item.content_type,
    fileName,
    kind,
    existingAttachmentId: item.id,
    ...(text !== null ? { pasted: { chars: charCount(text), preview: pastedTextPreview(text) } } : {}),
  };
}
