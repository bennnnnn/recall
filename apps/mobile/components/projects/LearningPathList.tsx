import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { ProjectItemRow } from "@/components/ProjectItemRow";
import type { PathChapterProgress, ProjectItem, ProjectListGroup, VocabStatus } from "@/lib/api";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  pathProgress: PathChapterProgress[];
  upNext?: string | null;
  lists: ProjectListGroup[];
  speechLanguage: string;
  busyId: string | null;
  onStatusChange: (itemId: string, status: VocabStatus) => void | Promise<void>;
};

function listKey(title: string): string {
  return title.trim().toLowerCase();
}

export function LearningPathList({
  pathProgress,
  upNext,
  lists,
  speechLanguage,
  busyId,
  onStatusChange,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [openTitle, setOpenTitle] = useState<string | null>(upNext ?? null);

  const itemsByChapter = useMemo(() => {
    const map = new Map<string, ProjectItem[]>();
    for (const group of lists) {
      map.set(listKey(group.list_title), group.items);
    }
    return map;
  }, [lists]);

  if (pathProgress.length === 0) {
    return (
      <View style={s.card}>
        <Text style={s.heading}>{t("projects.chapters_title")}</Text>
        <Text style={s.hint}>{t("projects.chapters_hint")}</Text>
      </View>
    );
  }

  const done = pathProgress.filter((chapter) => chapter.complete).length;

  return (
    <View style={s.card}>
      <Text style={s.heading}>{t("projects.chapters_title")}</Text>
      <Text style={s.meta}>
        {t("projects.chapters_progress", { done, total: pathProgress.length })}
      </Text>
      {upNext ? (
        <Text style={s.upNext}>{t("projects.chapters_up_next", { chapter: upNext })}</Text>
      ) : null}
      <Text style={s.hint}>{t("projects.chapters_expand_hint")}</Text>
      {pathProgress.map((chapter) => {
        const open = listKey(openTitle ?? "") === listKey(chapter.title);
        const words = itemsByChapter.get(listKey(chapter.title)) ?? [];
        return (
          <View key={chapter.title} style={s.chapter}>
            <Pressable
              style={s.chapterRow}
              onPress={() => setOpenTitle(open ? null : chapter.title)}
              accessibilityRole="button"
              accessibilityState={{ expanded: open }}
            >
              <Ionicons
                name={chapter.complete ? "checkmark-circle" : "ellipse-outline"}
                size={20}
                color={chapter.complete ? theme.primary : theme.textTertiary}
              />
              <View style={s.chapterMain}>
                <Text style={s.chapterTitle}>{chapter.title}</Text>
                <Text style={s.chapterMeta}>
                  {t("projects.journey_topic_progress", {
                    mastered: chapter.mastered,
                    total: chapter.total,
                  })}
                </Text>
              </View>
              <Ionicons
                name={open ? "chevron-up" : "chevron-down"}
                size={16}
                color={theme.textTertiary}
              />
            </Pressable>
            {open
              ? words.map((item) => (
                  <ProjectItemRow
                    key={item.id}
                    item={item}
                    showSpeech
                    speechLanguage={speechLanguage}
                    busy={busyId === item.id}
                    onStatusChange={onStatusChange}
                  />
                ))
              : null}
          </View>
        );
      })}
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    card: {
      backgroundColor: theme.surface,
      borderRadius: 16,
      padding: 14,
      gap: 10,
    },
    heading: {
      fontSize: 13,
      fontWeight: "700",
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
    },
    meta: { fontSize: 14, fontWeight: "600", color: theme.textSecondary },
    upNext: { fontSize: 14, fontWeight: "700", color: theme.primary },
    hint: { fontSize: 13, lineHeight: 18, color: theme.textSecondary },
    chapter: { gap: 8 },
    chapterRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingVertical: 6,
    },
    chapterMain: { flex: 1, gap: 2 },
    chapterTitle: { fontSize: 16, fontWeight: "700", color: theme.text },
    chapterMeta: { fontSize: 12, fontWeight: "600", color: theme.textTertiary },
  });
}
