import { useCallback, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useFocusEffect } from "expo-router";
import { useNavigation } from "expo-router";
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

type Filter = "all" | "generated" | "upload";

const PAGE_SIZE = 30;
const NUM_COLUMNS = 3;

export default function GalleryScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const insets = useSafeAreaInsets();
  const navigation = useNavigation();

  const [filter, setFilter] = useState<Filter>("all");
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
          source: filter === "all" ? undefined : filter,
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
      navigation.setOptions({ title: t("gallery.title") });
    }, [navigation, t]),
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
    { key: "generated", label: t("gallery.filter.generated") },
    { key: "upload", label: t("gallery.filter.uploaded") },
  ];

  const viewerItem = viewerIndex != null ? items[viewerIndex] ?? null : null;

  const renderItem = useCallback(
    ({ item, index }: { item: AttachmentListItem; index: number }) => (
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
    ),
    [t],
  );

  return (
    <View style={s.root}>
      <View style={[s.tabs, { marginTop: insets.top }]}>
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
              <Text style={[s.tabText, active && s.tabTextActive]}>{f.label}</Text>
            </Pressable>
          );
        })}
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
          data={items}
          keyExtractor={(item) => item.id}
          numColumns={NUM_COLUMNS}
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

const THUMB_SIZE = 108;

function makeStyles(C: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: C.bg },
    tabs: {
      flexDirection: "row",
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      gap: Space.xs,
    },
    tab: {
      paddingVertical: 7,
      paddingHorizontal: 14,
      borderRadius: 20,
      alignItems: "center",
      justifyContent: "center",
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
    content: { padding: Space.md, paddingBottom: 96 },
    gridGap: { height: Space.sm },
    footer: { paddingVertical: Space.md, alignItems: "center" },
  });
}
