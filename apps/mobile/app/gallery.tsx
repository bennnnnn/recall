import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useTranslation } from "react-i18next";

import { AttachmentImageViewer } from "@/components/AttachmentImageViewer";
import { GalleryColumnRow } from "@/components/gallery/GalleryColumnRow";
import { GalleryItemActionsSheet } from "@/components/gallery/GalleryItemActionsSheet";
import { GalleryLibraryHeader } from "@/components/gallery/GalleryLibraryHeader";
import { GalleryThumbnail } from "@/components/GalleryThumbnail";
import { Icon } from "@/components/Icon";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useGalleryData } from "@/hooks/useGalleryData";
import { useGalleryLibrary } from "@/hooks/useGalleryLibrary";
import { type AttachmentListItem } from "@/lib/api";
import {
  GALLERY_GRID_COLUMNS,
  galleryEmptyKey,
  galleryFileName,
  galleryPressAction,
  galleryThumbSize,
  type GalleryFilter,
} from "@/lib/gallery";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export default function GalleryScreen() {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const { width } = useWindowDimensions();
  const thumbSize = galleryThumbSize(width - Space.md * 2, GALLERY_GRID_COLUMNS, Space.xs);

  const [filter, setFilter] = useState<GalleryFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const {
    items,
    loading,
    loadingMore,
    error,
    pullRefreshing,
    refresh,
    loadMore,
    retry,
    removeItem,
  } = useGalleryData(filter, searchQuery);
  const library = useGalleryLibrary(items, removeItem);

  const renderItem = useCallback(
    ({ item }: { item: AttachmentListItem }) => {
      const fileName = galleryFileName(item.content_type, item.original_filename);
      const isImage = galleryPressAction(item.content_type) === "view-image";
      if (library.layout === "column") {
        return (
          <GalleryColumnRow
            item={item}
            fileName={fileName}
            onPress={() => (isImage ? library.openImage(item) : library.openActions(item))}
            onLongPress={() => library.openActions(item)}
            onMissing={removeItem}
          />
        );
      }
      if (isImage) {
        return (
          <Pressable
            onPress={() => library.openImage(item)}
            onLongPress={() => library.openActions(item)}
            accessibilityRole="button"
            accessibilityLabel={t("chat.image_view_a11y")}
          >
            <GalleryThumbnail
              attachmentId={item.id}
              downloadUrl={item.download_url}
              size={thumbSize}
              onMissing={removeItem}
            />
          </Pressable>
        );
      }
      return (
        <Pressable
          onPress={() => library.openActions(item)}
          onLongPress={() => library.openActions(item)}
          accessibilityRole="button"
          accessibilityLabel={t("gallery.file_actions_a11y")}
        >
          <View style={[s.fileTile, { width: thumbSize, height: thumbSize }]}>
            <Icon name="document-outline" size={32} color={C.textTertiary} />
            <Text style={s.fileLabel} numberOfLines={1}>
              {fileName}
            </Text>
          </View>
        </Pressable>
      );
    },
    [t, s, C, thumbSize, library, removeItem],
  );

  const viewerItem = library.viewerItem;

  return (
    <View style={s.root}>
      <GalleryLibraryHeader
        filter={filter}
        searchQuery={searchQuery}
        layout={library.layout}
        onSearchChange={setSearchQuery}
        onFilterChange={(next) => {
          library.setViewerId(null);
          setFilter(next);
        }}
        onToggleLayout={library.toggleLayout}
      />

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
          key={library.layout}
          data={items}
          keyExtractor={(item) => item.id}
          numColumns={library.layout === "grid" ? GALLERY_GRID_COLUMNS : 1}
          contentContainerStyle={s.content}
          ItemSeparatorComponent={
            library.layout === "grid" ? () => <View style={s.gridGap} /> : undefined
          }
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
              icon="library-outline"
              title={t(galleryEmptyKey(filter, searchQuery))}
            />
          }
          renderItem={renderItem}
        />
      )}

      <AttachmentImageViewer
        visible={viewerItem != null && galleryPressAction(viewerItem.content_type) === "view-image"}
        onClose={() => library.setViewerId(null)}
        attachmentId={viewerItem?.id}
        path={viewerItem?.download_url ?? null}
        fileName={
          viewerItem
            ? galleryFileName(viewerItem.content_type, viewerItem.original_filename)
            : undefined
        }
        onOpenChat={viewerItem?.chat_id ? () => library.openChat(viewerItem) : undefined}
        onDelete={viewerItem ? () => library.confirmDelete(viewerItem) : undefined}
      />

      <GalleryItemActionsSheet
        visible={library.actionItem != null}
        canOpenChat={Boolean(library.actionItem?.chat_id)}
        onClose={() => library.setActionItem(null)}
        onOpenChat={() => {
          const item = library.actionItem;
          library.setActionItem(null);
          if (item) library.openChat(item);
        }}
        onShare={() => {
          const item = library.actionItem;
          if (!item) return;
          void library.shareFile(item).then(() => library.setActionItem(null));
        }}
        onDelete={() => {
          const item = library.actionItem;
          if (!item) return;
          library.confirmDelete(item);
        }}
      />
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: C.bg },
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
