import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { ProjectItemRow } from "@/components/ProjectItemRow";
import { LearningContinueCta } from "@/components/projects/LearningContinueCta";
import { StateView } from "@/components/StateView";
import { api, type ProjectDailyHistoryDay, type ProjectItem, type VocabStatus } from "@/lib/api";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { weekdayFullLabel } from "@/lib/weekdayLabels";

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
  /** Optional embedded map from a fat detail payload; omit to lazy-load via /daily-items. */
  itemsByDate?: Record<string, ProjectItem[]>;
  /** Optional embedded misses; omit to lazy-load via /daily-items?bucket=missed. */
  missedItems?: ProjectItem[];
  onItemUpdated?: () => void;
};

export function ProjectDayItemsList({
  token,
  projectId,
  activityDate,
  dayMeta,
  isTrivia = false,
  studyAction = null,
  itemsByDate,
  missedItems: missedItemsProp,
  onItemUpdated,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const cachedItems = itemsByDate ? (itemsByDate[activityDate] ?? []) : undefined;
  const useEmbedded =
    itemsByDate !== undefined && missedItemsProp !== undefined;
  const [items, setItems] = useState<ProjectItem[]>(cachedItems ?? []);
  const [missedItems, setMissedItems] = useState<ProjectItem[]>(missedItemsProp ?? []);
  const [loading, setLoading] = useState(!useEmbedded && cachedItems === undefined);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [page, missed] = await Promise.all([
        api.getProjectDailyItems(token, projectId, activityDate, {
          limit: PAGE_SIZE,
          offset: 0,
          bucket: "mastered",
        }),
        api.getProjectDailyItems(token, projectId, activityDate, {
          limit: PAGE_SIZE,
          offset: 0,
          bucket: "missed",
        }),
      ]);
      setItems(page);
      setMissedItems(missed);
    } catch {
      setItems([]);
      setMissedItems([]);
    } finally {
      setLoading(false);
    }
  }, [token, projectId, activityDate]);

  useEffect(() => {
    if (useEmbedded) {
      setItems(itemsByDate?.[activityDate] ?? []);
      setMissedItems(missedItemsProp ?? []);
      setLoading(false);
      return;
    }
    if (itemsByDate) {
      setItems(itemsByDate[activityDate] ?? []);
      setLoading(false);
      // Still fetch misses when only mastered map was embedded.
      void (async () => {
        try {
          const missed = await api.getProjectDailyItems(token, projectId, activityDate, {
            limit: PAGE_SIZE,
            offset: 0,
            bucket: "missed",
          });
          setMissedItems(missed);
        } catch {
          setMissedItems([]);
        }
      })();
      return;
    }
    void load();
  }, [
    activityDate,
    itemsByDate,
    load,
    missedItemsProp,
    projectId,
    token,
    useEmbedded,
  ]);

  const handleStatusChange = useCallback(
    async (itemId: string, status: VocabStatus) => {
      setBusyId(itemId);
      try {
        const updated = await api.updateProjectItem(token, projectId, itemId, { status });
        setItems((prev) => prev.map((row) => (row.id === itemId ? updated : row)));
        setMissedItems((prev) => {
          if (status === "mastered") {
            return prev.filter((row) => row.id !== itemId);
          }
          return prev.map((row) => (row.id === itemId ? updated : row));
        });
        onItemUpdated?.();
      } catch {
        Alert.alert(t("common.error"), t("projects.status_update_failed"));
      } finally {
        setBusyId(null);
      }
    },
    [token, projectId, onItemUpdated, t],
  );

  const dayName = weekdayFullLabel(dayMeta?.weekday ?? 0, t);

  const emptyMessage = useMemo(() => {
    if (dayMeta?.status === "inactive") return t("projects.daily_items.empty_inactive");
    if (dayMeta?.status === "today") {
      return isTrivia
        ? t("projects.daily_items.empty_today_trivia")
        : t("projects.daily_items.empty_today");
    }
    return isTrivia
      ? t("projects.daily_items.empty_quiz_missed_day", { day: dayName })
      : t("projects.daily_items.empty_words_missed_day", { day: dayName });
  }, [dayMeta, dayName, isTrivia, t]);

  const title = isTrivia
    ? t("projects.daily_items.title_facts", { day: dayName })
    : t("projects.daily_items.title_words", { day: dayName });
  const missedTitle = t("projects.daily_items.title_missed", { day: dayName });

  return (
    <View style={s.wrap}>
      {missedItems.length > 0 ? (
        <View style={s.section}>
          <Text style={s.label}>{missedTitle}</Text>
          <View style={s.items}>
            {missedItems.map((item) => (
              <View key={`missed-${item.id}`} style={s.itemCard}>
                <ProjectItemRow
                  item={item}
                  showSpeech={!isTrivia}
                  busy={busyId === item.id}
                  onStatusChange={handleStatusChange}
                />
              </View>
            ))}
          </View>
        </View>
      ) : null}

      <View style={s.section}>
        <View style={s.header}>
          <Text style={s.label}>{title}</Text>
        </View>

      {loading ? (
        <StateView variant="loading" compact />
      ) : items.length === 0 ? (
        <View style={s.emptyBlock}>
          <Text style={s.empty}>{emptyMessage}</Text>
          {studyAction ? (
            <LearningContinueCta
              label={studyAction.label}
              onPress={studyAction.onPress}
              variant="outline"
            />
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
                  onStatusChange={handleStatusChange}
                />
              </View>
            ))}
          </View>
          {studyAction ? (
            <LearningContinueCta
              label={studyAction.label}
              onPress={studyAction.onPress}
              variant="outline"
            />
          ) : null}
        </View>
      )}
      </View>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: {
      gap: 16,
    },
    section: {
      gap: 10,
    },
    header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
    label: {
      ...Type.caption,
      fontWeight: "700",
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
    },
    emptyBlock: { gap: 12 },
    itemsBlock: { gap: 16 },
    empty: {
      ...Type.secondary,
      color: theme.textSecondary,
      backgroundColor: theme.surface,
      borderRadius: 14,
      padding: 16,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    items: { gap: 16 },
    itemCard: {
      backgroundColor: theme.surface,
      borderRadius: 14,
      borderWidth: 1.5,
      borderColor: theme.isDark ? theme.border : theme.bg,
      padding: 14,
    },
  });
}
