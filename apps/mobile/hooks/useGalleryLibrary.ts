import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Alert } from "react-native";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { useAuthToken } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { getSessionGeneration } from "@/lib/auth";
import { api, type AttachmentListItem } from "@/lib/api";
import { resolveAttachmentUri } from "@/lib/attachmentUri";
import { removeCachedGalleryItem } from "@/lib/cache/galleryListCache";
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
import { queueComposerAttachment } from "@/lib/pendingComposerAttachment";
import { pendingFromLibraryItem } from "@/lib/pendingFromLibraryItem";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

export function useGalleryLibrary(
  items: AttachmentListItem[],
  removeItem: (id: string) => void,
) {
  const { t } = useTranslation();
  const router = useRouter();
  const token = useAuthToken();
  const session = getSessionGeneration();
  const params = useLocalSearchParams<{ composerThread?: string | string[] }>();
  const targetThread = Array.isArray(params.composerThread) ? params.composerThread[0] : params.composerThread;
  const feedback = useActionFeedbackOptional();
  const [layout, setLayoutState] = useState<GalleryLayout>(peekGalleryLayout);
  const [viewerId, setViewerId] = useState<string | null>(null);
  const [actionItem, setActionItem] = useState<AttachmentListItem | null>(null);
  const sharingRef = useRef(false);
  const attachingRef = useRef(false);
  const deletingRef = useRef(new Set<string>());
  const layoutEditedRef = useRef(false);
  const viewRef = useRef({ focused: true, version: 0 });
  useFocusEffect(useCallback(() => {
    viewRef.current.focused = true;
    return () => { viewRef.current.focused = false; viewRef.current.version++; };
  }, []));
  const isCurrent = useCallback((version: number) =>
    viewRef.current.focused && viewRef.current.version === version && session === getSessionGeneration(), [session]);
  useLayoutEffect(() => {
    setActionItem(null);
    setViewerId(null);
  }, [session]);

  useEffect(() => {
    let cancelled = false;
    void getGalleryLayout().then((saved) => {
      if (!cancelled && !layoutEditedRef.current) setLayoutState(saved);
    });
    return () => { cancelled = true; };
  }, []);

  const viewerItem = viewerId ? items.find((item) => item.id === viewerId) ?? null : null;

  const setLayout = useCallback((next: GalleryLayout) => {
    layoutEditedRef.current = true;
    setLayoutState(next);
    void persistGalleryLayout(next);
  }, []);

  const toggleLayout = useCallback(() => {
    tap();
    setLayout(layout === "grid" ? "column" : "grid");
  }, [layout, setLayout]);

  const shareFile = useCallback(
    async (item: AttachmentListItem) => {
      const version = viewRef.current.version;
      if (!token || !isCurrent(version) || sharingRef.current) return;
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
        if (isCurrent(version)) setActionItem((current) => current?.id === item.id ? null : current);
      } catch (shareError) {
        if (!isCurrent(version)) return;
        reportRecoverableError(
          feedback,
          shareError instanceof Error ? shareError.message : t("common.error"),
        );
      } finally {
        sharingRef.current = false;
      }
    },
    [t, token, feedback, isCurrent],
  );

  const openChat = useCallback(
    (item: AttachmentListItem) => {
      const href = libraryOpenChatHref(item);
      if (!href) return;
      router.push(href);
    },
    [router],
  );

  const attachToComposer = useCallback(
    async (item: AttachmentListItem) => {
      const version = viewRef.current.version;
      if (!token || !isCurrent(version) || attachingRef.current) return;
      attachingRef.current = true;
      try {
        const pending = await pendingFromLibraryItem(item, token);
        if (!isCurrent(version)) return;
        queueComposerAttachment(pending, targetThread);
        setActionItem(null);
        setViewerId(null);
        if (router.canGoBack()) router.back();
        else router.replace("/");
      } catch (attachError) {
        if (!isCurrent(version)) return;
        reportRecoverableError(
          feedback,
          attachError instanceof Error ? attachError.message : t("chat.attach_failed"),
        );
      } finally {
        attachingRef.current = false;
      }
    },
    [feedback, router, t, token, isCurrent, targetThread],
  );

  const deleteItem = useCallback(
    async (item: AttachmentListItem) => {
      const version = viewRef.current.version;
      if (!token || !isCurrent(version) || deletingRef.current.has(item.id)) return;
      deletingRef.current.add(item.id);
      try {
        await api.deleteAttachment(token, item.id);
        if (session !== getSessionGeneration()) return;
        removeCachedGalleryItem(item.id);
        if (item.chat_id) void clearCachedChatMessages(item.chat_id);
        if (!isCurrent(version)) return;
        removeItem(item.id);
        setViewerId((current) => (current === item.id ? null : current));
        setActionItem((current) => (current?.id === item.id ? null : current));
      } catch (deleteError) {
        if (!isCurrent(version)) return;
        reportRecoverableError(
          feedback,
          deleteError instanceof Error ? deleteError.message : t("gallery.delete_failed"),
        );
      } finally {
        deletingRef.current.delete(item.id);
      }
    },
    [token, removeItem, feedback, t, isCurrent, session],
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
    attachToComposer,
    confirmDelete,
    openActions,
    openImage,
  };
}
