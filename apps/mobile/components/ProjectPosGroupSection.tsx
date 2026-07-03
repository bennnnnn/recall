import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { ProjectItemRow } from "@/components/ProjectItemRow";
import { Theme, useTheme } from "@/lib/theme";
import { api, type ProjectItem, type ProjectPosGroupSummary, type VocabStatus } from "@/lib/api";

export const VOCAB_PAGE_SIZE = 25;

type Props = {
  token: string;
  projectId: string;
  group: ProjectPosGroupSummary;
  onSpeechUnavailable?: () => void;
  onItemUpdated?: () => void;
};

export function ProjectPosGroupItems({
  token,
  projectId,
  group,
  onSpeechUnavailable,
  onItemUpdated,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [items, setItems] = useState<ProjectItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const loadPage = useCallback(
    async (offset: number, append: boolean) => {
      if (append) setLoadingMore(true);
      else setLoading(true);
      try {
        const page = await api.getProjectPosItems(token, projectId, group.part_of_speech, {
          limit: VOCAB_PAGE_SIZE,
          offset,
        });
        setItems((prev) => {
          const next = append ? [...prev, ...page] : page;
          setHasMore(page.length === VOCAB_PAGE_SIZE && next.length < group.count);
          return next;
        });
      } catch {
        if (!append) setItems([]);
        setHasMore(false);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [token, projectId, group.part_of_speech, group.count],
  );

  useEffect(() => {
    setItems([]);
    setHasMore(false);
    void loadPage(0, false);
  }, [loadPage]);

  const handleStatusChange = useCallback(
    async (itemId: string, status: VocabStatus) => {
      setBusyId(itemId);
      try {
        const updated = await api.updateProjectItem(token, projectId, itemId, { status });
        setItems((prev) => prev.map((row) => (row.id === itemId ? updated : row)));
        onItemUpdated?.();
      } catch {
        const { Alert } = await import("react-native");
        Alert.alert(t("common.error"), t("projects.status_update_failed"));
      } finally {
        setBusyId(null);
      }
    },
    [token, projectId, onItemUpdated, t],
  );

  const remaining = Math.max(0, group.count - items.length);

  if (loading) {
    return <ActivityIndicator color={theme.primary} style={s.loader} />;
  }

  if (items.length === 0) {
    return <Text style={s.empty}>{t("projects.pos_group_empty")}</Text>;
  }

  return (
    <View style={s.items}>
      <Text style={s.countLine}>
        {t("projects.words_showing", { shown: items.length, total: group.count })}
      </Text>
      {items.map((item, index) => (
        <View key={item.id}>
          {index > 0 ? <View style={s.divider} /> : null}
          <ProjectItemRow
            item={item}
            busy={busyId === item.id}
            onStatusChange={(status) => handleStatusChange(item.id, status)}
            onSpeechUnavailable={onSpeechUnavailable}
          />
        </View>
      ))}
      {hasMore ? (
        <Pressable
          style={[s.loadMoreBtn, loadingMore && s.loadMoreBtnBusy]}
          disabled={loadingMore}
          onPress={() => void loadPage(items.length, true)}
        >
          {loadingMore ? (
            <ActivityIndicator color={theme.primary} />
          ) : (
            <Text style={s.loadMoreText}>
              {t("projects.words_load_more", { count: Math.min(remaining, VOCAB_PAGE_SIZE) })}
            </Text>
          )}
        </Pressable>
      ) : null}
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    loader: { paddingVertical: 20 },
    empty: { fontSize: 14, color: theme.textSecondary, paddingVertical: 8 },
    items: { gap: 0 },
    countLine: {
      fontSize: 12,
      fontWeight: "600",
      color: theme.textTertiary,
      marginBottom: 10,
    },
    divider: {
      height: StyleSheet.hairlineWidth,
      backgroundColor: theme.border,
      marginVertical: 12,
    },
    loadMoreBtn: {
      marginTop: 12,
      paddingVertical: 12,
      borderRadius: 12,
      backgroundColor: theme.bg,
      borderWidth: 1,
      borderColor: theme.border,
      alignItems: "center",
      justifyContent: "center",
      minHeight: 44,
    },
    loadMoreBtnBusy: { opacity: 0.7 },
    loadMoreText: { fontSize: 14, fontWeight: "700", color: theme.primary },
  });
}
