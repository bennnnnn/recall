import { useCallback, useMemo, useState } from "react";
import {
  Alert,
  LayoutAnimation,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  UIManager,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { ProjectItemRow } from "@/components/ProjectItemRow";
import type { ProjectItem, ProjectListGroup, VocabStatus } from "@/lib/api";
import { api } from "@/lib/api";
import { programmingChapterIndex } from "@/lib/programmingCurriculum";
import { suggestProgrammingTopic } from "@/lib/programmingStudy";
import { Theme, useTheme } from "@/lib/theme";

if (Platform.OS === "android" && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

function itemMastered(item: ProjectItem): boolean {
  return item.status === "mastered" || item.mastered;
}

function chapterProgress(group: ProjectListGroup) {
  const total = group.items.length;
  const mastered = group.items.filter(itemMastered).length;
  return {
    total,
    mastered,
    complete: total > 0 && mastered === total,
  };
}

type Props = {
  token: string;
  projectId: string;
  lists: ProjectListGroup[];
  onItemUpdated?: () => void;
};

export function ProgrammingJourney({ token, projectId, lists, onItemUpdated }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const nextChapter = useMemo(() => suggestProgrammingTopic(lists), [lists]);
  const chaptersComplete = useMemo(
    () => lists.filter((group) => chapterProgress(group).complete).length,
    [lists],
  );

  const toggleChapter = (title: string) => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setExpanded((prev) => ({ ...prev, [title]: !prev[title] }));
  };

  const handleStatusChange = useCallback(
    async (itemId: string, status: VocabStatus) => {
      setBusyId(itemId);
      try {
        await api.updateProjectItem(token, projectId, itemId, { status });
        onItemUpdated?.();
      } catch {
        Alert.alert(t("common.error"), t("projects.status_update_failed"));
      } finally {
        setBusyId(null);
      }
    },
    [token, projectId, onItemUpdated, t],
  );

  if (lists.length === 0) return null;

  return (
    <View style={s.wrap}>
      <View style={s.header}>
        <Text style={s.heading}>{t("projects.chapters_title")}</Text>
        <Text style={s.badge}>
          {t("projects.chapters_progress", { done: chaptersComplete, total: lists.length })}
        </Text>
      </View>
      {nextChapter ? (
        <View style={s.nextBox}>
          <Ionicons name="book-outline" size={18} color={theme.primary} />
          <Text style={s.nextText}>{t("projects.chapters_up_next", { chapter: nextChapter })}</Text>
        </View>
      ) : (
        <Text style={s.doneText}>{t("projects.journey_all_done")}</Text>
      )}
      <Text style={s.hint}>{t("projects.chapters_expand_hint")}</Text>
      <View style={s.list}>
        {lists.map((group, index) => {
          const progress = chapterProgress(group);
          const chapterNum = programmingChapterIndex(group.list_title) || index + 1;
          const isNext = group.list_title === nextChapter;
          const open = expanded[group.list_title] === true;
          return (
            <View key={group.list_title} style={index > 0 ? s.chapterBlockBorder : undefined}>
              <Pressable
                style={[s.chapterHeader, isNext && s.chapterHeaderNext]}
                onPress={() => toggleChapter(group.list_title)}
                accessibilityRole="button"
                accessibilityState={{ expanded: open }}
              >
                <View style={[s.chapterIndex, progress.complete && s.chapterIndexDone]}>
                  {progress.complete ? (
                    <Ionicons name="checkmark" size={16} color={theme.primary} />
                  ) : (
                    <Text style={[s.chapterIndexText, isNext && s.chapterIndexTextNext]}>
                      {chapterNum}
                    </Text>
                  )}
                </View>
                <View style={s.chapterHeaderMain}>
                  <Text style={s.chapterTitle}>{group.list_title}</Text>
                  <Text style={s.chapterMeta}>
                    {t("projects.chapter_topics_progress", {
                      done: progress.mastered,
                      total: progress.total,
                    })}
                  </Text>
                  <View style={s.track}>
                    <View
                      style={[
                        s.fill,
                        {
                          width:
                            progress.total > 0
                              ? `${Math.round((progress.mastered / progress.total) * 100)}%`
                              : "0%",
                        },
                      ]}
                    />
                  </View>
                </View>
                <Ionicons
                  name={open ? "chevron-up" : "chevron-down"}
                  size={20}
                  color={theme.textTertiary}
                />
              </Pressable>
              {open ? (
                <View style={s.chapterBody}>
                  <Text style={s.topicsLabel}>{t("projects.chapter_topics_label")}</Text>
                  {group.items.map((item, topicIndex) => (
                    <View key={item.id}>
                      {topicIndex > 0 ? <View style={s.divider} /> : null}
                      <ProjectItemRow
                        item={item}
                        showSpeech={false}
                        busy={busyId === item.id}
                        onStatusChange={(status) => handleStatusChange(item.id, status)}
                      />
                    </View>
                  ))}
                </View>
              ) : null}
            </View>
          );
        })}
      </View>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: { gap: 10 },
    header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
    heading: {
      fontSize: 13,
      fontWeight: "700",
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
    },
    badge: {
      fontSize: 12,
      fontWeight: "700",
      color: theme.primary,
      backgroundColor: theme.primaryLight,
      paddingHorizontal: 10,
      paddingVertical: 4,
      borderRadius: 999,
    },
    nextBox: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: 8,
      backgroundColor: theme.primaryLight,
      borderRadius: 12,
      padding: 12,
    },
    nextText: { flex: 1, fontSize: 14, lineHeight: 20, color: theme.text, fontWeight: "600" },
    doneText: { fontSize: 14, lineHeight: 20, color: theme.primary, fontWeight: "600" },
    hint: { fontSize: 14, color: theme.textSecondary, lineHeight: 20 },
    list: {
      backgroundColor: theme.surface,
      borderRadius: 16,
      overflow: "hidden",
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    chapterBlockBorder: {
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: theme.border,
    },
    chapterHeader: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      padding: 14,
    },
    chapterHeaderNext: { backgroundColor: theme.bg },
    chapterIndex: {
      width: 28,
      height: 28,
      borderRadius: 8,
      backgroundColor: theme.bg,
      alignItems: "center",
      justifyContent: "center",
    },
    chapterIndexDone: { backgroundColor: theme.primaryLight },
    chapterIndexText: { fontSize: 13, fontWeight: "800", color: theme.textSecondary },
    chapterIndexTextNext: { color: theme.primary },
    chapterHeaderMain: { flex: 1, gap: 6 },
    chapterTitle: { fontSize: 16, fontWeight: "700", color: theme.text },
    chapterMeta: { fontSize: 13, color: theme.textSecondary },
    track: {
      height: 4,
      borderRadius: 2,
      backgroundColor: theme.border,
      overflow: "hidden",
    },
    fill: { height: 4, borderRadius: 2, backgroundColor: theme.primary },
    chapterBody: {
      paddingHorizontal: 14,
      paddingBottom: 14,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: theme.border,
      backgroundColor: theme.bg,
      gap: 8,
    },
    topicsLabel: {
      fontSize: 12,
      fontWeight: "700",
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.5,
    },
    divider: {
      height: StyleSheet.hairlineWidth,
      backgroundColor: theme.border,
      marginVertical: 10,
    },
  });
}
