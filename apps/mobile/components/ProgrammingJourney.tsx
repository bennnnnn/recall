import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import type { ProjectItem, ProjectListGroup } from "@/lib/api";
import { suggestProgrammingTopic } from "@/lib/programmingStudy";
import { Theme, useTheme } from "@/lib/theme";

function itemMastered(item: ProjectItem): boolean {
  return item.status === "mastered" || item.mastered;
}

function itemLearning(item: ProjectItem): boolean {
  return item.status === "learning";
}

function topicStats(items: ProjectItem[]) {
  const total = items.length;
  const mastered = items.filter(itemMastered).length;
  const learning = items.filter(itemLearning).length;
  return { total, mastered, learning, pending: total - mastered };
}

function statusIcon(item: ProjectItem): keyof typeof Ionicons.glyphMap {
  if (itemMastered(item)) return "checkmark-circle";
  if (itemLearning(item)) return "ellipse";
  return "ellipse-outline";
}

function statusColor(item: ProjectItem, theme: Theme): string {
  if (itemMastered(item)) return theme.primary;
  if (itemLearning(item)) return "#FF9F0A";
  return theme.textTertiary;
}

type Props = {
  lists: ProjectListGroup[];
  onStudyTopic?: (topic: string) => void;
};

export function ProgrammingJourney({ lists, onStudyTopic }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const suggestion = useMemo(() => suggestProgrammingTopic(lists), [lists]);
  const allMastered = useMemo(
    () => lists.length > 0 && lists.every((g) => topicStats(g.items).pending === 0),
    [lists],
  );

  if (lists.length === 0) return null;

  return (
    <View style={s.wrap}>
      <Text style={s.heading}>{t("projects.journey_title")}</Text>
      {allMastered ? (
        <Text style={s.suggestion}>{t("projects.journey_all_done")}</Text>
      ) : suggestion ? (
        <View style={s.suggestionBox}>
          <Ionicons name="bulb-outline" size={18} color={theme.primary} />
          <Text style={s.suggestion}>
            {t("projects.journey_suggestion", { topic: suggestion })}
          </Text>
        </View>
      ) : null}

      {lists.map((group) => {
        const stats = topicStats(group.items);
        const open = expanded[group.list_title] ?? (stats.pending > 0 && stats.mastered === 0);
        const progress = stats.total > 0 ? stats.mastered / stats.total : 0;
        return (
          <View key={group.list_title} style={s.topicCard}>
            <Pressable
              style={s.topicHeader}
              onPress={() =>
                setExpanded((prev) => ({
                  ...prev,
                  [group.list_title]: !open,
                }))
              }
            >
              <View style={s.topicHeaderMain}>
                <Text style={s.topicTitle}>{group.list_title}</Text>
                <Text style={s.topicMeta}>
                  {t("projects.journey_topic_progress", {
                    mastered: stats.mastered,
                    total: stats.total,
                  })}
                </Text>
                <View style={s.progressTrack}>
                  <View style={[s.progressFill, { width: `${Math.round(progress * 100)}%` }]} />
                </View>
              </View>
              <Ionicons
                name={open ? "chevron-up" : "chevron-down"}
                size={18}
                color={theme.textTertiary}
              />
            </Pressable>
            {open ? (
              <View style={s.topicBody}>
                {group.items.map((item) => (
                  <View key={item.id} style={s.itemRow}>
                    <Ionicons name={statusIcon(item)} size={18} color={statusColor(item, theme)} />
                    <Text
                      style={[s.itemText, itemMastered(item) && s.itemMastered]}
                      numberOfLines={2}
                    >
                      {item.content}
                    </Text>
                  </View>
                ))}
                {onStudyTopic ? (
                  <Pressable style={s.topicStudyBtn} onPress={() => onStudyTopic(group.list_title)}>
                    <Text style={s.topicStudyText}>
                      {t("projects.journey_study_topic", { topic: group.list_title })}
                    </Text>
                  </Pressable>
                ) : null}
              </View>
            ) : null}
          </View>
        );
      })}
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: { gap: 10 },
    heading: {
      fontSize: 13,
      fontWeight: "700",
      color: theme.textSecondary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
    },
    suggestionBox: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: 8,
      backgroundColor: theme.primaryLight,
      borderRadius: 12,
      padding: 12,
    },
    suggestion: { flex: 1, fontSize: 14, lineHeight: 20, color: theme.text, fontWeight: "600" },
    topicCard: {
      backgroundColor: theme.surface,
      borderRadius: 16,
      overflow: "hidden",
    },
    topicHeader: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      padding: 14,
    },
    topicHeaderMain: { flex: 1, gap: 6 },
    topicTitle: { fontSize: 16, fontWeight: "700", color: theme.text },
    topicMeta: { fontSize: 13, color: theme.textSecondary },
    progressTrack: {
      height: 6,
      borderRadius: 3,
      backgroundColor: theme.border,
      overflow: "hidden",
    },
    progressFill: { height: 6, borderRadius: 3, backgroundColor: theme.primary },
    topicBody: { paddingHorizontal: 14, paddingBottom: 14, gap: 8 },
    itemRow: { flexDirection: "row", alignItems: "flex-start", gap: 10 },
    itemText: { flex: 1, fontSize: 15, lineHeight: 21, color: theme.text },
    itemMastered: { color: theme.textSecondary },
    topicStudyBtn: {
      marginTop: 4,
      alignSelf: "flex-start",
      paddingVertical: 8,
      paddingHorizontal: 12,
      borderRadius: 10,
      backgroundColor: theme.primaryLight,
    },
    topicStudyText: { fontSize: 13, fontWeight: "700", color: theme.primary },
  });
}
