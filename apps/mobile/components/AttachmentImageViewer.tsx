import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  FlatList,
  Modal,
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
import { AttachmentLightboxChrome } from "@/components/AttachmentLightboxChrome";
import { useAuthToken } from "@/contexts/AuthContext";
import { useSheetPanDismiss } from "@/hooks/useSheetPanDismiss";
import { saveChatAttachmentToLibrary, shareChatAttachment } from "@/lib/downloadChatAttachment";
import { resolveAttachmentUri } from "@/lib/attachmentUri";
import { useReduceMotion } from "@/lib/reduceMotion";

const LIGHTBOX_BG = "#000000";

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
  const [chromeVisible, setChromeVisible] = useState(true);
  const [overflowOpen, setOverflowOpen] = useState(false);
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
      setChromeVisible(true);
      setOverflowOpen(false);
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
  const showUseInChat = Boolean(onUseInChat && current);
  const showOpenChat = Boolean(onOpenChat && current?.chatId);
  const showDelete = Boolean(onDelete && current);
  const showOverflow = showUseInChat || showOpenChat || showDelete;

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

  const onImagePress = () => {
    if (overflowOpen) {
      setOverflowOpen(false);
      return;
    }
    setChromeVisible((open) => !open);
  };

  const stage = (item: AttachmentViewerImage, active: boolean) => (
    <AttachmentImageStage item={item} active={active} onPress={onImagePress} />
  );

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
                    {stage(item, visible && Math.abs(index - pageIndex) <= 1)}
                  </View>
                )}
              />
            ) : (
              stage(items[0] ?? { previewUri }, visible)
            )}

            <AttachmentLightboxChrome
              visible={chromeVisible}
              overflowOpen={overflowOpen}
              insets={insets}
              busy={busy}
              canShare={Boolean(remoteUri)}
              showOverflow={showOverflow}
              showUseInChat={showUseInChat}
              showOpenChat={showOpenChat}
              showDelete={showDelete}
              showDots={showDots}
              pageIndex={pageIndex}
              pageCount={items.length}
              onClose={onClose}
              onShare={() => void handleShare()}
              onDownload={() => void handleDownload()}
              onToggleOverflow={() => setOverflowOpen((open) => !open)}
              onCloseOverflow={() => setOverflowOpen(false)}
              onUseInChat={() => {
                if (!current || !onUseInChat) return;
                setOverflowOpen(false);
                onUseInChat(current);
              }}
              onOpenChat={() => {
                if (!current || !onOpenChat) return;
                setOverflowOpen(false);
                onOpenChat(current);
              }}
              onDelete={() => {
                if (!current || !onDelete) return;
                setOverflowOpen(false);
                onDelete(current);
              }}
            />
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
});
