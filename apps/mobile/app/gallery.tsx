import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
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
import { type AttachmentListItem } from "@/lib/api";
import { type GalleryFilter, useGalleryData } from "@/hooks/useGalleryData";
import { tap } from "@/lib/haptics";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type ViewMode = "grid" | "list";

const NUM_COLUMNS = 3;
const THUMB_SIZE = 112;

function isImageType(contentType: string): boolean {
  return contentType.startsWith("image/");
}

export default function GalleryScreen() {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const insets = useSafeAreaInsets();
  const navigation = useNavigation();

  const [filter, setFilter] = useState<GalleryFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [viewerIndex, setViewerIndex] = useState<number | null>(null);
  const {
    items,
    filteredItems,
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
    { key: "images", label: t("gallery.filter.images") },
    { key: "files", label: t("gallery.filter.files") },
  ];

  const viewerItem =
    viewerIndex != null ? filteredItems[viewerIndex] ?? null : null;

  const renderItem = useCallback(
    ({ item, index }: { item: AttachmentListItem; index: number }) => {
      if (isImageType(item.content_type)) {
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
              size={THUMB_SIZE}
            />
          </Pressable>
        );
      }
      // File/document tile
      return (
        <Pressable
          onPress={() => {
            tap();
            setViewerIndex(index);
          }}
          accessibilityRole="button"
          accessibilityLabel={t("chat.image_view_a11y")}
        >
          <View style={s.fileTile}>
            <Icon name="document-outline" size={32} color={C.textTertiary} />
            <Text style={s.fileLabel} numberOfLines={1}>
              {item.content_type.split("/").pop() ?? "file"}
            </Text>
          </View>
        </Pressable>
      );
    },
    [t, s, C],
  );

  return (
    <View style={s.root}>
      {/* Header: title on its own line, search bar below, then tabs + view toggle */}
      <View style={[s.header, { paddingTop: insets.top + Space.sm }]}>
        <Text style={s.title}>{t("gallery.title")}</Text>

        <View style={s.searchBar}>
          <Icon name="search-outline" size={16} color={C.textTertiary} />
          <TextInput
            style={s.searchInput}
            placeholder={t("gallery.search_placeholder")}
            placeholderTextColor={C.textTertiary}
            value={searchQuery}
            onChangeText={setSearchQuery}
            autoCorrect={false}
            returnKeyType="search"
          />
        </View>

        <View style={s.subRow}>
          <View style={s.tabs}>
            {filters.map((f) => {
              const active = f.key === filter;
              return (
                <Pressable
                  key={f.key}
                  style={[s.tab, active && s.tabActive]}
                  onPress={() => {
                    tap();
                    setFilter(f.key);
                  }}
                  accessibilityRole="button"
                  accessibilityState={{ selected: active }}
                >
                  <Text style={[s.tabText, active && s.tabTextActive]}>
                    {f.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          <View style={s.viewToggles}>
            <Pressable
              style={[s.viewBtn, viewMode === "grid" && s.viewBtnActive]}
              onPress={() => {
                tap();
                setViewMode("grid");
              }}
              accessibilityRole="button"
              accessibilityState={{ selected: viewMode === "grid" }}
            >
              <Icon
                name="grid-outline"
                size={16}
                color={viewMode === "grid" ? C.text : C.textTertiary}
              />
            </Pressable>
            <Pressable
              style={[s.viewBtn, viewMode === "list" && s.viewBtnActive]}
              onPress={() => {
                tap();
                setViewMode("list");
              }}
              accessibilityRole="button"
              accessibilityState={{ selected: viewMode === "list" }}
            >
              <Icon
                name="list-outline"
                size={16}
                color={viewMode === "list" ? C.text : C.textTertiary}
              />
            </Pressable>
          </View>
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
          data={filteredItems}
          keyExtractor={(item) => item.id}
          numColumns={viewMode === "grid" ? NUM_COLUMNS : 1}
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
              title={t("gallery.empty")}
            />
          }
          renderItem={renderItem}
        />
      )}

      <AttachmentImageViewer
        visible={viewerItem != null}
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
    searchBar: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      height: 40,
      paddingHorizontal: 14,
      borderRadius: 20,
      borderWidth: 1,
      borderColor: C.border,
      backgroundColor: C.surface,
      marginBottom: Space.sm,
    },
    searchInput: {
      flex: 1,
      ...Type.body,
      fontSize: 15,
      padding: 0,
      color: C.text,
    },
    subRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
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
    viewToggles: {
      flexDirection: "row",
      alignItems: "center",
      gap: 4,
    },
    viewBtn: {
      width: 30,
      height: 30,
      borderRadius: 15,
      alignItems: "center",
      justifyContent: "center",
    },
    viewBtnActive: {
      backgroundColor: C.surfaceAlt,
    },
    content: {
      padding: Space.md,
      paddingBottom: 96,
    },
    gridGap: { height: Space.sm },
    footer: {
      paddingVertical: Space.md,
      alignItems: "center",
    },
    fileTile: {
      width: THUMB_SIZE,
      height: THUMB_SIZE,
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
