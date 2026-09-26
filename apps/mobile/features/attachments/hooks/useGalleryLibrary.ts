import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { useAuthToken } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { getSessionGeneration } from "@/lib/auth";
import { api, type AttachmentListItem } from "@/lib/api";
import { resolveAttachmentUri } from "@/features/attachments/model/attachmentUri";
import { removeCachedGalleryItem } from "@/features/attachments/model/galleryListCache";
import { clearCachedChatMessages } from "@/lib/chat/messageCache";
import { shareChatAttachment } from "@/features/attachments/model/downloadChatAttachment";
import { galleryFileName, isReadableTextContentType, libraryOpenChatHref } from "@/features/attachments/model/gallery";
import { isPdfContentType } from "@/lib/messageAttachments";
import {
  getGalleryLayout,
  peekGalleryLayout,
  setGalleryLayout as persistGalleryLayout,
  type GalleryLayout,
} from "@/features/attachments/model/galleryLayout";
import { selection, tap } from "@/lib/haptics";
import { queueComposerAttachment } from "@/features/attachments/model/pendingComposerAttachment";
import { pendingFromLibraryItem } from "@/lib/pendingFromLibraryItem";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { confirmDialog } from "@/ui/overlay/dialogs";

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
  const [fileItem, setFileItem] = useState<AttachmentListItem | null>(null);
  const [actionItem, setActionItem] = useState<AttachmentListItem | null>(null);
  const [actionPoint, setActionPoint] = useState<{ x: number; y: number } | null>(null);
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
    setFileItem(null);
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
        setFileItem(null);
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
        setFileItem((current) => (current?.id === item.id ? null : current));
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
      void confirmDialog({
        title: t("gallery.delete_confirm_title"),
        message: t("gallery.delete_confirm_body"),
        cancelLabel: t("common.cancel"),
        confirmLabel: t("common.delete"),
        destructive: true,
      }).then((ok) => {
        if (ok) void deleteItem(item);
      });
    },
    [t, deleteItem],
  );

  const openActions = useCallback(
    (item: AttachmentListItem, point?: { x: number; y: number }) => {
      selection();
      setActionPoint(point ?? null);
      setActionItem(item);
    },
    [],
  );

  const openImage = useCallback((item: AttachmentListItem) => {
    tap();
    setFileItem(null);
    setViewerId(item.id);
  }, []);

  const openFile = useCallback(
    (item: AttachmentListItem) => {
      tap();
      setViewerId(null);
      if (isPdfContentType(item.content_type) || isReadableTextContentType(item.content_type)) {
        setFileItem(item);
        return;
      }
      return shareFile(item);
    },
    [shareFile],
  );

  return {
    layout,
    toggleLayout,
    viewerItem,
    setViewerId,
    fileItem,
    setFileItem,
    actionItem,
    actionPoint,
    setActionItem,
    shareFile,
    openChat,
    attachToComposer,
    confirmDelete,
    openActions,
    openImage,
    openFile,
  };
}
