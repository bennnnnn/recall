import { useCallback, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useFocusEffect, useNavigation, useRouter } from "expo-router";
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
  const navigation = useNavigation();
  const router = useRouter();
  const token = useAuthToken();
  const { width } = useWindowDimensions();
  const thumbSize = galleryThumbSize(width - Space.md * 2, NUM_COLUMNS, Space.xs);

  const [filter, setFilter] = useState<GalleryFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
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
  } = useGalleryData(filter, searchQuery);

  useFocusEffect(
    useCallback(() => {
      navigation.setOptions({ title: "" });
    }, [navigation]),
  );

  const filters: { key: GalleryFilter; label: string }[] = [
    { key: "all", label: t("gallery.filter.all") },
    { key: "generated", label: t("gallery.filter.generated") },
    { key: "uploaded", label: t("gallery.filter.uploaded") },
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
          fileName: galleryFileName(item.content_type, item.original_filename),
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

  const openChat = useCallback(() => {
    if (!viewerItem?.chat_id) return;
    router.replace({
      pathname: "/",
      params: {
        chatId: viewerItem.chat_id,
        ...(viewerItem.message_id
          ? { highlightMessage: viewerItem.message_id }
          : {}),
      },
    });
  }, [router, viewerItem]);

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
              {item.original_filename?.trim() ||
                item.content_type.split("/").pop() ||
                "file"}
            </Text>
          </View>
        </Pressable>
      );
    },
    [t, s, C, thumbSize, shareFile],
  );

  return (
    <View style={s.root}>
      <View style={s.header}>
        <View style={s.searchBar}>
          <Icon name="search-outline" size={16} color={C.textTertiary} />
          <TextInput
            style={s.searchInput}
            placeholder={t("gallery.search_placeholder")}
            placeholderTextColor={C.textDisabled}
            value={searchQuery}
            onChangeText={setSearchQuery}
            autoCorrect={false}
            returnKeyType="search"
          />
        </View>
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
      ) : error && items.length === 0 ? (
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
        onOpenChat={viewerItem?.chat_id ? openChat : undefined}
      />
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: C.bg },
    header: {
      paddingHorizontal: Space.md,
      paddingTop: Space.sm,
      paddingBottom: Space.sm,
    },
    searchBar: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      minHeight: 44,
      paddingHorizontal: 14,
      borderRadius: 20,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      backgroundColor: C.surfaceAlt,
      marginBottom: Space.sm,
    },
    searchInput: {
      flex: 1,
      ...Type.body,
      fontSize: 15,
      padding: 0,
      color: C.text,
    },
    tabs: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: Space.xs,
    },
    tab: {
      minHeight: 44,
      justifyContent: "center",
      paddingVertical: Space.xs,
      paddingHorizontal: 12,
      borderRadius: 20,
      flexGrow: 0,
      flexShrink: 0,
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
      backgroundColor: C.surfaceAlt,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
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
