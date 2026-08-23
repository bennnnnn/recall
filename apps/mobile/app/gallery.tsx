import { useCallback, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useFocusEffect, useNavigation } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { AttachmentImageViewer } from "@/components/AttachmentImageViewer";
import { GalleryThumbnail } from "@/components/GalleryThumbnail";
import { Icon } from "@/components/Icon";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAuthToken } from "@/contexts/AuthContext";
import { type AttachmentListItem } from "@/lib/api";
import { resolveAttachmentUri } from "@/lib/attachmentUri";
import { shareChatAttachment } from "@/lib/downloadChatAttachment";
import {
  galleryEmptyKey,
  galleryFileName,
  galleryPressAction,
  galleryThumbSize,
  type GalleryFilter,
} from "@/lib/gallery";
import { useGalleryData } from "@/hooks/useGalleryData";
import { tap } from "@/lib/haptics";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

const NUM_COLUMNS = 3;

export default function GalleryScreen() {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const insets = useSafeAreaInsets();
  const navigation = useNavigation();
  const token = useAuthToken();
  const { width } = useWindowDimensions();
  const thumbSize = galleryThumbSize(width - Space.md * 2, NUM_COLUMNS, Space.xs);

  const [filter, setFilter] = useState<GalleryFilter>("all");
  const [viewerIndex, setViewerIndex] = useState<number | null>(null);
  const sharingRef = useRef(false);
  const {
    items,
    loading,
    loadingMore,
    error,
    pullRefreshing,
    refresh,
    loadMore,
    retry,
  } = useGalleryData(filter);

  useFocusEffect(
    useCallback(() => {
      navigation.setOptions({ title: "" });
    }, [navigation]),
  );

  const filters: { key: GalleryFilter; label: string }[] = [
    { key: "all", label: t("gallery.filter.all") },
    { key: "images", label: t("gallery.filter.images") },
    { key: "files", label: t("gallery.filter.files") },
  ];

  const viewerItem = viewerIndex != null ? items[viewerIndex] ?? null : null;

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
          fileName: galleryFileName(item.content_type),
        });
      } catch (shareError) {
        Alert.alert(
          t("common.download_failed"),
          shareError instanceof Error ? shareError.message : t("common.error"),
        );
      } finally {
        sharingRef.current = false;
      }
    },
    [t, token],
  );

  const renderItem = useCallback(
    ({ item, index }: { item: AttachmentListItem; index: number }) => {
      const action = galleryPressAction(item.content_type);
      if (action === "view-image") {
        return (
          <Pressable
            onPress={() => {
              tap();
              setViewerIndex(index);
            }}
            accessibilityRole="button"
            accessibilityLabel={t("chat.image_view_a11y")}
          >
            <GalleryThumbnail
              attachmentId={item.id}
              downloadUrl={item.download_url}
              size={thumbSize}
            />
          </Pressable>
        );
      }
      return (
        <Pressable
          onPress={() => {
            tap();
            void shareFile(item);
          }}
          accessibilityRole="button"
          accessibilityLabel={t("gallery.share_file_a11y")}
        >
          <View style={[s.fileTile, { width: thumbSize, height: thumbSize }]}>
            <Icon name="document-outline" size={32} color={C.textTertiary} />
            <Text style={s.fileLabel} numberOfLines={1}>
              {item.content_type.split("/").pop() ?? "file"}
            </Text>
          </View>
        </Pressable>
      );
    },
    [t, s, C, thumbSize, shareFile],
  );

  return (
    <View style={s.root}>
      <View style={[s.header, { paddingTop: insets.top + Space.sm }]}>
        <Text style={s.title}>{t("gallery.title")}</Text>
        <View style={s.tabs}>
          {filters.map((tab) => {
            const active = tab.key === filter;
            return (
              <Pressable
                key={tab.key}
                style={[s.tab, active && s.tabActive]}
                onPress={() => {
                  tap();
                  setViewerIndex(null);
                  setFilter(tab.key);
                }}
                accessibilityRole="button"
                accessibilityState={{ selected: active }}
              >
                <Text style={[s.tabText, active && s.tabTextActive]}>
                  {tab.label}
                </Text>
              </Pressable>
            );
          })}
        </View>
      </View>

      {loading && items.length === 0 && !error ? (
        <SkeletonList />
      ) : error ? (
        <StateView
          variant="error"
          title={t("common.error")}
          onRetry={() => void retry({ reset: true })}
          retryLabel={t("common.retry")}
        />
      ) : (
        <FlashList
          data={items}
          keyExtractor={(item) => item.id}
          numColumns={NUM_COLUMNS}
          contentContainerStyle={s.content}
          ItemSeparatorComponent={() => <View style={s.gridGap} />}
          refreshControl={
            <RefreshControl
              refreshing={pullRefreshing}
              onRefresh={refresh}
              tintColor={C.primary}
            />
          }
          onEndReached={loadMore}
          onEndReachedThreshold={0.5}
          ListFooterComponent={
            loadingMore ? (
              <View style={s.footer}>
                <ActivityIndicator color={C.textTertiary} />
              </View>
            ) : null
          }
          ListEmptyComponent={
            <StateView
              variant="empty"
              icon="images-outline"
              title={t(galleryEmptyKey(filter))}
            />
          }
          renderItem={renderItem}
        />
      )}

      <AttachmentImageViewer
        visible={viewerItem != null && galleryPressAction(viewerItem.content_type) === "view-image"}
        onClose={() => setViewerIndex(null)}
        attachmentId={viewerItem?.id}
        path={viewerItem?.download_url ?? null}
      />
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: C.bg },
    header: {
      paddingHorizontal: Space.md,
      paddingBottom: Space.sm,
    },
    title: {
      fontSize: 28,
      fontWeight: "800",
      lineHeight: 34,
      color: C.text,
      marginBottom: Space.sm,
    },
    tabs: {
      flexDirection: "row",
      gap: Space.xs,
    },
    tab: {
      paddingVertical: 7,
      paddingHorizontal: 16,
      borderRadius: 20,
    },
    tabActive: {
      backgroundColor: C.surfaceAlt,
    },
    tabText: {
      ...Type.label,
      color: C.textSecondary,
      fontWeight: "500",
    },
    tabTextActive: {
      color: C.text,
      fontWeight: "600",
    },
    content: {
      paddingHorizontal: Space.md,
      paddingBottom: 96,
    },
    gridGap: { height: Space.xs },
    footer: {
      paddingVertical: Space.md,
      alignItems: "center",
    },
    fileTile: {
      borderRadius: 10,
      backgroundColor: C.surface,
      alignItems: "center",
      justifyContent: "center",
      gap: 6,
    },
    fileLabel: {
      ...Type.label,
      fontSize: 11,
      color: C.textTertiary,
      textTransform: "uppercase",
    },
  });
}
