import { useCallback, useMemo, useRef, useState } from "react";
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
import { useRouter, useFocusEffect, useNavigation } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { AttachmentImageViewer } from "@/components/AttachmentImageViewer";
import { GalleryThumbnail } from "@/components/GalleryThumbnail";
import { Icon } from "@/components/Icon";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAuth } from "@/contexts/AuthContext";
import { api, type AttachmentListItem } from "@/lib/api";
import { tap } from "@/lib/haptics";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Filter = "all" | "images" | "files";
type ViewMode = "grid" | "list";

const PAGE_SIZE = 30;
const NUM_COLUMNS = 3;
const THUMB_SIZE = 112;

function isImageType(contentType: string): boolean {
  return contentType.startsWith("image/");
}

export default function GalleryScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const insets = useSafeAreaInsets();
  const navigation = useNavigation();
  const router = useRouter();

  const [filter, setFilter] = useState<Filter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [items, setItems] = useState<AttachmentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [pullRefreshing, setPullRefreshing] = useState(false);
  const [viewerIndex, setViewerIndex] = useState<number | null>(null);
  const offsetRef = useRef(0);

  const load = useCallback(
    async (opts: { reset?: boolean; silent?: boolean } = {}) => {
      if (!token) return;
      const reset = opts.reset ?? true;
      if (!opts.silent) {
        if (reset) setLoading(true);
        else setLoadingMore(true);
      }
      try {
        const offset = reset ? 0 : offsetRef.current;
        const res = await api.listAttachments(token, {
          category: filter === "all" ? undefined : filter,
          limit: PAGE_SIZE,
          offset,
        });
        setItems((prev) => (reset ? res.items : [...prev, ...res.items]));
        setHasMore(res.has_more);
        offsetRef.current = offset + res.items.length;
        setError(null);
      } catch {
        setError(t("common.error"));
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [token, filter, t],
  );

  useFocusEffect(
    useCallback(() => {
      void load({ reset: true });
    }, [load]),
  );

  useFocusEffect(
    useCallback(() => {
      navigation.setOptions({ title: "" });
    }, [navigation]),
  );

  const onRefresh = useCallback(async () => {
    setPullRefreshing(true);
    await load({ reset: true, silent: true });
    setPullRefreshing(false);
  }, [load]);

  const onEndReached = useCallback(() => {
    if (!hasMore || loadingMore || loading) return;
    void load({ reset: false, silent: true });
  }, [hasMore, loadingMore, loading, load]);

  const filters: { key: Filter; label: string }[] = [
    { key: "all", label: t("gallery.filter.all") },
    { key: "images", label: t("gallery.filter.images") },
    { key: "files", label: t("gallery.filter.files") },
  ];

  // Client-side search filter on the loaded items
  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) return items;
    const q = searchQuery.toLowerCase();
    return items.filter(
      (item) =>
        item.source.toLowerCase().includes(q) ||
        item.content_type.toLowerCase().includes(q) ||
        item.id.toLowerCase().includes(q),
    );
  }, [items, searchQuery]);

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
      {/* Header — matches the Library design */}
      <View style={[s.header, { paddingTop: insets.top + Space.sm }]}>
        {/* Row 1: title + search + New button */}
        <View style={s.headerRow}>
          <Text style={s.title}>{t("gallery.title")}</Text>
          <View style={s.headerRight}>
            <View style={s.searchBar}>
              <Icon name="search-outline" size={16} color={C.textTertiary} />
              <TextInput
                style={s.searchInput}
                placeholder={t("search.placeholder")}
                placeholderTextColor={C.textTertiary}
                value={searchQuery}
                onChangeText={setSearchQuery}
                autoCorrect={false}
                returnKeyType="search"
              />
            </View>
            <Pressable
              style={s.newBtn}
              onPress={() => {
                tap();
                router.replace("/");
              }}
              accessibilityRole="button"
              accessibilityLabel={t("gallery.new")}
            >
              <Text style={s.newBtnText}>{t("gallery.new")}</Text>
              <Icon name="chevron-down" size={14} color="#fff" />
            </Pressable>
          </View>
        </View>

        {/* Row 2: tabs + view toggle */}
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
          onRetry={() => void load({ reset: true })}
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
              onRefresh={onRefresh}
              tintColor={C.primary}
            />
          }
          onEndReached={onEndReached}
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
    headerRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: Space.sm,
    },
    title: {
      fontSize: 28,
      fontWeight: "800",
      lineHeight: 34,
      color: C.text,
    },
    headerRight: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      flexShrink: 1,
    },
    searchBar: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      flex: 1,
      height: 36,
      paddingHorizontal: 12,
      borderRadius: 20,
      borderWidth: 1,
      borderColor: C.border,
      backgroundColor: C.surface,
    },
    searchInput: {
      flex: 1,
      ...Type.body,
      fontSize: 14,
      padding: 0,
      color: C.text,
    },
    newBtn: {
      flexDirection: "row",
      alignItems: "center",
      gap: 4,
      height: 36,
      paddingHorizontal: 16,
      borderRadius: 20,
      backgroundColor: C.text,
    },
    newBtnText: {
      fontSize: 14,
      fontWeight: "600",
      color: C.bg,
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
