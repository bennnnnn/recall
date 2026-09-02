import { useCallback, useEffect, useRef, useState } from "react";
import { Alert } from "react-native";
import { useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { useAuthToken } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { api, type AttachmentListItem } from "@/lib/api";
import { resolveAttachmentUri } from "@/lib/attachmentUri";
import { clearCachedChatMessages } from "@/lib/chatMessageCache";
import { shareChatAttachment } from "@/lib/downloadChatAttachment";
import { galleryFileName, libraryOpenChatHref } from "@/lib/gallery";
import {
  getGalleryLayout,
  peekGalleryLayout,
  setGalleryLayout as persistGalleryLayout,
  type GalleryLayout,
} from "@/lib/galleryLayout";
import { selection, tap } from "@/lib/haptics";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

export function useGalleryLibrary(
  items: AttachmentListItem[],
  removeItem: (id: string) => void,
) {
  const { t } = useTranslation();
  const router = useRouter();
  const token = useAuthToken();
  const feedback = useActionFeedbackOptional();
  const [layout, setLayoutState] = useState<GalleryLayout>(peekGalleryLayout);
  const [viewerId, setViewerId] = useState<string | null>(null);
  const [actionItem, setActionItem] = useState<AttachmentListItem | null>(null);
  const sharingRef = useRef(false);

  useEffect(() => {
    void getGalleryLayout().then(setLayoutState);
  }, []);

  const viewerItem = viewerId ? items.find((item) => item.id === viewerId) ?? null : null;

  const setLayout = useCallback((next: GalleryLayout) => {
    setLayoutState(next);
    void persistGalleryLayout(next);
  }, []);

  const toggleLayout = useCallback(() => {
    tap();
    setLayout(layout === "grid" ? "column" : "grid");
  }, [layout, setLayout]);

  const shareFile = useCallback(
    async (item: AttachmentListItem) => {
      if (sharingRef.current) return;
      const uri = resolveAttachmentUri({
        attachmentId: item.id,
        path: item.download_url,
      });
      if (!uri) return;
      sharingRef.current = true;
      try {
        await shareChatAttachment({
          uri,
          token,
          fileName: galleryFileName(item.content_type, item.original_filename),
        });
      } catch (shareError) {
        reportRecoverableError(
          feedback,
          shareError instanceof Error ? shareError.message : t("common.error"),
        );
      } finally {
        sharingRef.current = false;
      }
    },
    [t, token, feedback],
  );

  const openChat = useCallback(
    (item: AttachmentListItem) => {
      const href = libraryOpenChatHref(item);
      if (!href) return;
      router.push(href);
    },
    [router],
  );

  const deleteItem = useCallback(
    async (item: AttachmentListItem) => {
      if (!token) return;
      try {
        await api.deleteAttachment(token, item.id);
        removeItem(item.id);
        if (item.chat_id) void clearCachedChatMessages(item.chat_id);
        setViewerId((current) => (current === item.id ? null : current));
        setActionItem((current) => (current?.id === item.id ? null : current));
      } catch (deleteError) {
        reportRecoverableError(
          feedback,
          deleteError instanceof Error ? deleteError.message : t("gallery.delete_failed"),
        );
      }
    },
    [token, removeItem, feedback, t],
  );

  const confirmDelete = useCallback(
    (item: AttachmentListItem) => {
      Alert.alert(t("gallery.delete_confirm_title"), t("gallery.delete_confirm_body"), [
        { text: t("common.cancel"), style: "cancel" },
        {
          text: t("common.delete"),
          style: "destructive",
          onPress: () => void deleteItem(item),
        },
      ]);
    },
    [t, deleteItem],
  );

  const openActions = useCallback((item: AttachmentListItem) => {
    selection();
    setActionItem(item);
  }, []);

  const openImage = useCallback((item: AttachmentListItem) => {
    tap();
    setViewerId(item.id);
  }, []);

  return {
    layout,
    toggleLayout,
    viewerItem,
    setViewerId,
    actionItem,
    setActionItem,
    shareFile,
    openChat,
    confirmDelete,
    openActions,
    openImage,
  };
}
