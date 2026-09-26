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
import { useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";

import { GalleryColumnRow } from "@/features/attachments/components/GalleryColumnRow";
import { GalleryLibraryHeader } from "@/features/attachments/components/GalleryLibraryHeader";
import { GalleryMediaModals } from "@/features/attachments/components/GalleryMediaModals";
import { GalleryThumbnail } from "@/features/attachments/components/GalleryThumbnail";
import { Icon } from "@/ui/icons/Icon";
import { SkeletonList } from "@/ui/feedback/SkeletonLoader";
import { StateView } from "@/ui/feedback/StateView";
import { useGalleryData } from "@/features/attachments/hooks/useGalleryData";
import { useGalleryLibrary } from "@/features/attachments/hooks/useGalleryLibrary";
import { type AttachmentListItem } from "@/lib/api";
import {
  GALLERY_GRID_COLUMNS,
  galleryEmptyKey,
  galleryFileName,
  galleryPressAction,
  galleryThumbSize,
  type GalleryFilter,
} from "@/features/attachments/model/gallery";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Radius } from "@/lib/radius";
import { IconSize } from "@/ui/icons/sizes";

export default function GalleryScreen() {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const { width } = useWindowDimensions();
  const thumbSize = galleryThumbSize(width - Space.md * 2, GALLERY_GRID_COLUMNS, Space.xs);
  const pickParam = useLocalSearchParams<{ pick?: string | string[] }>().pick;
  const pickMode = (Array.isArray(pickParam) ? pickParam[0] : pickParam) === "1";

  const [filter, setFilter] = useState<GalleryFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const {
    items,
    loading,
    loadingMore,
    error,
    pageError,
    retryPage,
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
      const onPress = () => {
        if (pickMode) {
          void library.attachToComposer(item);
          return;
        }
        if (isImage) library.openImage(item);
        else library.openFile(item);
      };
      if (library.layout === "column") {
        return (
          <GalleryColumnRow
            item={item}
            fileName={fileName}
            onPress={onPress}
            onLongPress={(point) => {
              if (!pickMode) library.openActions(item, point);
            }}
            onMissing={removeItem}
          />
        );
      }
      if (isImage) {
        return (
          <Pressable
            onPress={onPress}
            onLongPress={(event) => {
              if (!pickMode) {
                library.openActions(item, { x: event.nativeEvent.pageX, y: event.nativeEvent.pageY });
              }
            }}
            accessibilityRole="button"
            accessibilityLabel={
              pickMode ? t("gallery.use_in_chat") : t("chat.image_view_a11y")
            }
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
          onPress={onPress}
          onLongPress={(event) => {
            if (!pickMode) {
              library.openActions(item, { x: event.nativeEvent.pageX, y: event.nativeEvent.pageY });
            }
          }}
          accessibilityRole="button"
          accessibilityLabel={
            pickMode ? t("gallery.use_in_chat") : t("gallery.open_file_a11y")
          }
        >
          <View style={[s.fileTile, { width: thumbSize, height: thumbSize }]}>
            <Icon name="file" size={IconSize.xl} color={C.textTertiary} />
            <Text style={s.fileLabel} numberOfLines={1}>
              {fileName}
            </Text>
          </View>
        </Pressable>
      );
    },
    [t, s, C, thumbSize, library, pickMode, removeItem],
  );

  return (
    <View style={s.root}>
      <GalleryLibraryHeader
        filter={filter}
        searchQuery={searchQuery}
        layout={library.layout}
        onSearchChange={setSearchQuery}
        onFilterChange={(next) => {
          library.setViewerId(null);
          library.setFileItem(null);
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
            ) : pageError ? (
              <StateView variant="error" title={t("common.error")}
                onRetry={() => void retryPage()} retryLabel={t("common.retry")} />
            ) : null
          }
          ListEmptyComponent={
            <StateView
              variant="empty"
              icon="images"
              title={t(galleryEmptyKey(filter, searchQuery))}
              message={
                searchQuery.trim()
                  ? undefined
                  : t("gallery.empty_hint")
              }
            />
          }
          renderItem={renderItem}
        />
      )}

      <GalleryMediaModals items={items} pickMode={pickMode} library={library} />
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
      borderRadius: Radius.sm,
      backgroundColor: C.surfaceAlt,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      alignItems: "center",
      justifyContent: "center",
      gap: 6,
    },
    fileLabel: {
      ...Type.overline,
      ...Weight.semibold,
      color: C.textTertiary,
    },
  });
}
