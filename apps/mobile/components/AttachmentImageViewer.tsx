import { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  View,
  useWindowDimensions,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from "react-native";
import { GestureDetector, GestureHandlerRootView } from "react-native-gesture-handler";
import Animated from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { AttachmentImageStage, type AttachmentViewerImage } from "@/components/AttachmentImageStage";
import { Icon } from "@/components/Icon";
import { useAuthToken } from "@/contexts/AuthContext";
import { useSheetPanDismiss } from "@/hooks/useSheetPanDismiss";
import { saveChatAttachmentToLibrary, shareChatAttachment } from "@/lib/downloadChatAttachment";
import { resolveAttachmentUri } from "@/lib/attachmentUri";
import { Radius } from "@/lib/radius";
import { useReduceMotion } from "@/lib/reduceMotion";
import { Space } from "@/lib/space";

const LIGHTBOX_BG = "#000000";
const LIGHTBOX_FG = "#FFFFFF";
/** Circular chip behind each header icon so they read on the photo. */
const ICON_CHIP_BG = "rgba(255, 255, 255, 0.18)";

type Props = {
  visible: boolean;
  onClose: () => void;
  images?: AttachmentViewerImage[];
  initialIndex?: number;
  attachmentId?: string | null;
  localUri?: string | null;
  path?: string | null;
  fileName?: string;
  /** Already-resolved display URI from the chat thumbnail (instant open). */
  previewUri?: string | null;
  /** Open the originating chat (gallery). */
  onOpenChat?: (image: AttachmentViewerImage) => void;
  /** Attach this Library item to the composer. */
  onUseInChat?: (image: AttachmentViewerImage) => void;
  /** Remove this Library item (gallery). */
  onDelete?: (image: AttachmentViewerImage) => void;
};

export function AttachmentImageViewer({
  visible,
  onClose,
  images,
  initialIndex = 0,
  attachmentId,
  localUri,
  path,
  fileName = "image.jpg",
  previewUri = null,
  onOpenChat,
  onUseInChat,
  onDelete,
}: Props) {
  const { t } = useTranslation();
  const token = useAuthToken();
  const insets = useSafeAreaInsets();
  const { width: screenWidth } = useWindowDimensions();
  const reduceMotion = useReduceMotion();
  const { pan, panStyle, translateY } = useSheetPanDismiss(true, reduceMotion, onClose);
  const [busy, setBusy] = useState<"download" | "share" | null>(null);
  const [pageIndex, setPageIndex] = useState(initialIndex);
  const wasVisibleRef = useRef(false);

  const items = useMemo((): AttachmentViewerImage[] => {
    if (images && images.length > 0) return images;
    return [{ attachmentId, localUri, path, fileName, previewUri }];
  }, [images, attachmentId, localUri, path, fileName, previewUri]);

  const safeIndex = Math.min(Math.max(0, initialIndex), Math.max(0, items.length - 1));
  const showDots = items.length > 1 && items.length <= 8;

  useEffect(() => {
    if (visible && !wasVisibleRef.current) {
      setPageIndex(safeIndex);
    }
    wasVisibleRef.current = visible;
  }, [visible, safeIndex]);

  useEffect(() => {
    if (!visible) return;
    // Reanimated shared values are designed to be mutated from effects —
    // reset so a leftover drag doesn't reopen mid-slide.
    // eslint-disable-next-line react-hooks/immutability
    translateY.value = 0;
  }, [visible, translateY]);

  const current = items[Math.min(pageIndex, items.length - 1)] ?? items[0];
  const remoteUri = resolveAttachmentUri({
    attachmentId: current?.attachmentId,
    localUri: current?.localUri,
    path: current?.path,
  });
  const currentName = current?.fileName ?? fileName;

  const handleDownload = async () => {
    if (!remoteUri || busy) return;
    setBusy("download");
    try {
      const result = await saveChatAttachmentToLibrary({
        uri: remoteUri,
        token,
        fileName: currentName,
      });
      if (result === "saved") {
        Alert.alert(t("common.saved"), t("common.saved_to_photos"));
      }
    } catch (error) {
      Alert.alert(
        t("common.download_failed"),
        error instanceof Error ? error.message : t("common.download_image_error"),
      );
    } finally {
      setBusy(null);
    }
  };

  const handleShare = async () => {
    if (!remoteUri || busy) return;
    setBusy("share");
    try {
      await shareChatAttachment({
        uri: remoteUri,
        token,
        fileName: currentName,
      });
    } catch (error) {
      Alert.alert(
        t("common.share_failed"),
        error instanceof Error ? error.message : t("common.share_image_error"),
      );
    } finally {
      setBusy(null);
    }
  };

  const onPageScrollEnd = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const next = Math.round(event.nativeEvent.contentOffset.x / screenWidth);
    if (next >= 0 && next < items.length) setPageIndex(next);
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      presentationStyle="overFullScreen"
      statusBarTranslucent
      onRequestClose={onClose}
    >
      <GestureHandlerRootView style={s.flex}>
        <GestureDetector gesture={pan}>
          <Animated.View
            testID="attachment-image-viewer"
            collapsable={false}
            style={[s.root, panStyle]}
          >
        <View style={[s.header, { paddingTop: Math.max(insets.top, Space.xs) }]}>
          <Pressable
            style={s.iconBtn}
            onPress={onClose}
            hitSlop={8}
            accessibilityLabel={t("preview.close")}
          >
            <Icon name="close" size={22} color={LIGHTBOX_FG} />
          </Pressable>

          <View style={s.headerActions}>
            {onUseInChat && current ? (
              <Pressable
                style={s.iconBtn}
                onPress={() => onUseInChat(current)}
                hitSlop={8}
                accessibilityLabel={t("gallery.use_in_chat")}
              >
                <Icon name="attach-outline" size={22} color={LIGHTBOX_FG} />
              </Pressable>
            ) : null}
            {onOpenChat && current?.chatId ? (
              <Pressable
                style={s.iconBtn}
                onPress={() => onOpenChat(current)}
                hitSlop={8}
                accessibilityLabel={t("gallery.open_chat_a11y")}
              >
                <Icon name="chatbubble-outline" size={22} color={LIGHTBOX_FG} />
              </Pressable>
            ) : null}
            <Pressable
              style={[s.iconBtn, busy === "share" && s.iconBtnDisabled]}
              onPress={() => void handleShare()}
              disabled={!remoteUri || busy != null}
              hitSlop={8}
              accessibilityLabel={t("preview.share")}
            >
              {busy === "share" ? (
                <ActivityIndicator color={LIGHTBOX_FG} size="small" />
              ) : (
                <Icon name="share-outline" size={22} color={LIGHTBOX_FG} />
              )}
            </Pressable>
            <Pressable
              style={[s.iconBtn, busy === "download" && s.iconBtnDisabled]}
              onPress={() => void handleDownload()}
              disabled={!remoteUri || busy != null}
              hitSlop={8}
              accessibilityLabel={t("common.download")}
            >
              {busy === "download" ? (
                <ActivityIndicator color={LIGHTBOX_FG} size="small" />
              ) : (
                <Icon name="download-outline" size={22} color={LIGHTBOX_FG} />
              )}
            </Pressable>
            {onDelete && current ? (
              <Pressable
                style={s.iconBtn}
                onPress={() => onDelete(current)}
                hitSlop={8}
                accessibilityLabel={t("common.delete")}
              >
                <Icon name="trash-outline" size={22} danger />
              </Pressable>
            ) : null}
          </View>
        </View>

        {items.length > 1 ? (
          <FlatList
            testID="attachment-viewer-pager"
            style={s.pager}
            data={items}
            key={visible ? `open-${safeIndex}` : "closed"}
            horizontal
            pagingEnabled
            nestedScrollEnabled
            showsHorizontalScrollIndicator={false}
            keyExtractor={(item, index) =>
              `${item.attachmentId ?? item.path ?? item.localUri ?? "img"}-${index}`
            }
            getItemLayout={(_, index) => ({
              length: screenWidth,
              offset: screenWidth * index,
              index,
            })}
            initialScrollIndex={safeIndex}
            onScrollToIndexFailed={() => undefined}
            onMomentumScrollEnd={onPageScrollEnd}
            renderItem={({ item, index }) => (
              <View style={{ width: screenWidth, height: "100%" }}>
                <AttachmentImageStage item={item} active={visible && Math.abs(index - pageIndex) <= 1} />
              </View>
            )}
          />
        ) : (
          <AttachmentImageStage item={items[0] ?? { previewUri }} active={visible} />
        )}

        {showDots ? (
          <View style={[s.dots, { paddingBottom: Math.max(insets.bottom, Space.sm) }]}>
            {items.map((item, index) => (
              <View
                key={`${item.attachmentId ?? item.path ?? index}-dot`}
                style={[s.dot, index === pageIndex && s.dotActive]}
              />
            ))}
          </View>
        ) : (
          <View style={{ height: Math.max(insets.bottom, Space.sm) }} />
        )}
          </Animated.View>
        </GestureDetector>
      </GestureHandlerRootView>
    </Modal>
  );
}

const s = StyleSheet.create({
  flex: {
    flex: 1,
  },
  root: {
    flex: 1,
    backgroundColor: LIGHTBOX_BG,
  },
  pager: {
    flex: 1,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: Space.sm,
    paddingBottom: Space.xs,
  },
  headerActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: Space.xs,
  },
  iconBtn: {
    width: Space.minTouch,
    height: Space.minTouch,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: Radius.full,
    backgroundColor: ICON_CHIP_BG,
  },
  iconBtnDisabled: {
    opacity: 0.45,
  },
  dots: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    gap: 6,
    paddingTop: Space.xs,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "rgba(255,255,255,0.35)",
  },
  dotActive: {
    backgroundColor: LIGHTBOX_FG,
  },
});
