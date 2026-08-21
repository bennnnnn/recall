import { useCallback, useMemo } from "react";
import { Alert, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { ProjectItemRow } from "@/components/ProjectItemRow";
import { LearningContinueCta } from "@/components/projects/LearningContinueCta";
import { StateView } from "@/components/StateView";
import { type ProjectDailyHistoryDay, type ProjectItem, type VocabStatus } from "@/lib/api";
import { useProjectDayItems } from "@/hooks/useProjectDayItems";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { weekdayFullLabel } from "@/lib/weekdayLabels";

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
  speechLanguage?: string;
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
  speechLanguage = "en-US",
  studyAction = null,
  itemsByDate,
  missedItems: missedItemsProp,
  onItemUpdated,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { items, missedItems, loading, busyId, loadError, load, changeStatus } =
    useProjectDayItems({
      token,
      projectId,
      activityDate,
      itemsByDate,
      missedItems: missedItemsProp,
      onItemUpdated,
    });

  const handleStatusChange = useCallback(
    async (itemId: string, status: VocabStatus) => {
      const updated = await changeStatus(itemId, status);
      if (!updated) {
        Alert.alert(t("common.error"), t("projects.status_update_failed"));
      }
    },
    [changeStatus, t],
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
                  speechLanguage={speechLanguage}
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
      ) : loadError ? (
        <StateView
          variant="error"
          compact
          message={t("projects.load_failed")}
          onRetry={() => void load()}
          retryLabel={t("common.retry")}
        />
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
                  speechLanguage={speechLanguage}
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
      gap: Space.md,
    },
    section: {
      gap: Space.xs,
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: Space.xs,
    },
    label: {
      ...Type.caption,
      fontWeight: "700",
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
    },
    emptyBlock: { gap: Space.sm },
    itemsBlock: { gap: Space.md },
    empty: {
      ...Type.secondary,
      color: theme.textSecondary,
      backgroundColor: theme.surface,
      borderRadius: 14,
      padding: Space.md,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    items: { gap: Space.md },
    itemCard: {
      backgroundColor: theme.surface,
      borderRadius: 14,
      borderWidth: 1.5,
      borderColor: theme.isDark ? theme.border : theme.bg,
      padding: Space.sm,
    },
  });
}
