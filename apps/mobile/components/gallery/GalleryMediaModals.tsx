import { useMemo } from "react";

import { AttachmentImageViewer } from "@/components/AttachmentImageViewer";
import { AttachmentPdfViewer } from "@/components/AttachmentPdfViewer";
import { AttachmentTextViewer } from "@/components/AttachmentTextViewer";
import { GalleryItemActionsSheet } from "@/components/gallery/GalleryItemActionsSheet";
import { useGalleryLibrary } from "@/hooks/useGalleryLibrary";
import type { AttachmentListItem } from "@/lib/api";
import {
  galleryFileName,
  galleryImageIndex,
  galleryImageItems,
  galleryPressAction,
  isReadableTextContentType,
} from "@/lib/gallery";
import { isPdfContentType } from "@/lib/messageAttachments";

type Props = {
  items: AttachmentListItem[];
  pickMode: boolean;
  library: ReturnType<typeof useGalleryLibrary>;
};

export function GalleryMediaModals({ items, pickMode, library }: Props) {
  const viewerItem = library.viewerItem;
  const fileItem = library.fileItem;
  const images = useMemo(() => galleryImageItems(items), [items]);
  const viewerImages = useMemo(
    () =>
      images.map((item) => ({
        attachmentId: item.id,
        path: item.download_url,
        fileName: galleryFileName(item.content_type, item.original_filename),
        chatId: item.chat_id ?? null,
      })),
    [images],
  );
  const viewerIndex = viewerItem ? galleryImageIndex(images, viewerItem.id) : 0;

  const itemForId = (id?: string | null) => items.find((item) => item.id === id);

  return (
    <>
      <AttachmentImageViewer
        visible={viewerItem != null && galleryPressAction(viewerItem.content_type) === "view-image"}
        onClose={() => library.setViewerId(null)}
        images={viewerImages}
        initialIndex={viewerIndex}
        onOpenChat={(image) => {
          const item = itemForId(image.attachmentId);
          library.setViewerId(null);
          if (item?.chat_id) library.openChat(item);
        }}
        onUseInChat={(image) => {
          const item = itemForId(image.attachmentId);
          if (item) void library.attachToComposer(item);
        }}
        onDelete={(image) => {
          const item = itemForId(image.attachmentId);
          if (item) library.confirmDelete(item);
        }}
      />

      <AttachmentPdfViewer
        visible={fileItem != null && isPdfContentType(fileItem.content_type)}
        onClose={() => library.setFileItem(null)}
        attachmentId={fileItem?.id}
        path={fileItem?.download_url ?? null}
        fileName={
          fileItem
            ? galleryFileName(fileItem.content_type, fileItem.original_filename)
            : "document.pdf"
        }
        onShare={() => {
          if (fileItem) void library.shareFile(fileItem);
        }}
      />

      <AttachmentTextViewer
        visible={fileItem != null && isReadableTextContentType(fileItem.content_type)}
        onClose={() => library.setFileItem(null)}
        attachmentId={fileItem?.id}
        path={fileItem?.download_url ?? null}
        fileName={
          fileItem
            ? galleryFileName(fileItem.content_type, fileItem.original_filename)
            : "file.txt"
        }
        onShare={() => {
          if (fileItem) void library.shareFile(fileItem);
        }}
      />

      <GalleryItemActionsSheet
        visible={!pickMode && library.actionItem != null}
        canOpenChat={Boolean(library.actionItem?.chat_id)}
        onClose={() => library.setActionItem(null)}
        onUseInChat={() => {
          const item = library.actionItem;
          if (item) void library.attachToComposer(item);
        }}
        onOpenChat={() => {
          const item = library.actionItem;
          library.setActionItem(null);
          if (item) library.openChat(item);
        }}
        onShare={() => {
          const item = library.actionItem;
          if (!item) return;
          void library.shareFile(item);
        }}
        onDelete={() => {
          const item = library.actionItem;
          if (!item) return;
          library.confirmDelete(item);
        }}
      />
    </>
  );
}
