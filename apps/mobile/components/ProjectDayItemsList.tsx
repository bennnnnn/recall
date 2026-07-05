import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { ProjectItemRow } from "@/components/ProjectItemRow";
import { api, type ProjectDailyHistoryDay, type ProjectItem, type VocabStatus } from "@/lib/api";
import { Theme, useTheme } from "@/lib/theme";

const PAGE_SIZE = 25;

export type ProjectStudyAction = {
  label: string;
  onPress: () => void;
};

type Props = {
  token: string;
  projectId: string;
  activityDate: string;
  dayMeta?: ProjectDailyHistoryDay;
  isTrivia?: boolean;
  studyAction?: ProjectStudyAction | null;
  itemsByDate?: Record<string, ProjectItem[]>;
  onItemUpdated?: () => void;
};

const WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;

export function ProjectDayItemsList({
  token,
  projectId,
  activityDate,
  dayMeta,
  isTrivia = false,
  studyAction = null,
  itemsByDate,
  onItemUpdated,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const cachedItems = itemsByDate ? (itemsByDate[activityDate] ?? []) : undefined;
  const [items, setItems] = useState<ProjectItem[]>(cachedItems ?? []);
  const [loading, setLoading] = useState(cachedItems === undefined);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const page = await api.getProjectDailyItems(token, projectId, activityDate, {
        limit: PAGE_SIZE,
        offset: 0,
      });
      setItems(page);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [token, projectId, activityDate]);

  useEffect(() => {
    if (itemsByDate) {
      setItems(itemsByDate[activityDate] ?? []);
      setLoading(false);
      return;
    }
    void load();
  }, [activityDate, itemsByDate, load]);

  const handleStatusChange = useCallback(
    async (itemId: string, status: VocabStatus) => {
      setBusyId(itemId);
      try {
        const updated = await api.updateProjectItem(token, projectId, itemId, { status });
        setItems((prev) => prev.map((row) => (row.id === itemId ? updated : row)));
        onItemUpdated?.();
      } catch {
        Alert.alert(t("common.error"), t("projects.status_update_failed"));
      } finally {
        setBusyId(null);
      }
    },
    [token, projectId, onItemUpdated, t],
  );

  const emptyKey = useMemo(() => {
    if (dayMeta?.status === "inactive") return "projects.daily_items.empty_inactive";
    if (dayMeta?.status === "skipped") return "projects.daily_items.empty_skipped";
    if (dayMeta?.status === "today") {
      return isTrivia ? "projects.daily_items.empty_today_trivia" : "projects.daily_items.empty_today";
    }
    if ((dayMeta?.mastered_count ?? 0) === 0) return "projects.daily_items.empty_skipped";
    return "projects.daily_items.empty_skipped";
  }, [dayMeta, isTrivia]);

  const title = isTrivia
    ? t("projects.daily_items.title_facts", { day: weekdayLabel(dayMeta, t) })
    : t("projects.daily_items.title_words", { day: weekdayLabel(dayMeta, t) });

  return (
    <View style={s.wrap}>
      <View style={s.header}>
        <Text style={s.label}>{title}</Text>
      </View>

      {loading ? (
        <ActivityIndicator color={theme.primary} style={s.loader} />
      ) : items.length === 0 ? (
        <View style={s.emptyBlock}>
          <Text style={s.empty}>{t(emptyKey)}</Text>
          {studyAction ? (
            <Pressable style={s.actionBtn} onPress={studyAction.onPress}>
              <Text style={s.actionBtnText}>{studyAction.label}</Text>
            </Pressable>
          ) : null}
        </View>
      ) : (
        <View style={s.itemsBlock}>
          <View style={s.items}>
            {items.map((item) => (
              <View key={item.id} style={s.itemCard}>
                <ProjectItemRow
                  item={item}
                  showSpeech={!isTrivia}
                  busy={busyId === item.id}
                  onStatusChange={(status) => handleStatusChange(item.id, status)}
                />
              </View>
            ))}
          </View>
          {studyAction ? (
            <Pressable style={s.actionBtn} onPress={studyAction.onPress}>
              <Text style={s.actionBtnText}>{studyAction.label}</Text>
            </Pressable>
          ) : null}
        </View>
      )}
    </View>
  );
}

function weekdayLabel(dayMeta: ProjectDailyHistoryDay | undefined, t: (key: string) => string): string {
  const key = WEEKDAY_KEYS[dayMeta?.weekday ?? 0] ?? "mon";
  return t(`projects.daily_strip.${key}`);
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: {
      gap: 10,
    },
    header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
    label: {
      fontSize: 13,
      fontWeight: "700",
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
    },
    loader: { paddingVertical: 16 },
    emptyBlock: { gap: 12 },
    itemsBlock: { gap: 12 },
    empty: {
      fontSize: 14,
      lineHeight: 20,
      color: theme.textSecondary,
      backgroundColor: theme.surface,
      borderRadius: 14,
      padding: 16,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    actionBtn: {
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: theme.surface,
      borderWidth: 1.5,
      borderColor: theme.primary,
      borderRadius: 14,
      paddingVertical: 14,
      paddingHorizontal: 16,
    },
    actionBtnText: { fontSize: 16, fontWeight: "600", color: theme.primary },
    items: { gap: 10 },
    itemCard: {
      backgroundColor: theme.surface,
      borderRadius: 14,
      borderWidth: 1.5,
      borderColor: theme.isDark ? theme.border : "#FFFFFF",
      padding: 14,
    },
  });
}
