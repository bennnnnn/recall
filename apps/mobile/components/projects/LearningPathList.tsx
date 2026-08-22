import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";
import { useTranslation } from "react-i18next";

import type { PathChapterProgress } from "@/lib/api";
import { chapterAccess } from "@/lib/projects/chapterAccess";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  pathProgress: PathChapterProgress[];
  upNext?: string | null;
  onOpenSection: (title: string) => void;
};

export function LearningPathList({ pathProgress, upNext, onOpenSection }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  if (pathProgress.length === 0) {
    return (
      <View style={s.card}>
        <Text style={s.heading}>{t("projects.chapters_title")}</Text>
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
      <View style={s.path}>
        {pathProgress.map((chapter, index) => {
          const access = chapterAccess(chapter, upNext);
          const initial = chapter.title.trim().charAt(0).toUpperCase() || "•";
          return (
            <View
              key={chapter.title}
              style={[s.nodeWrap, index % 2 === 1 ? s.nodeOffset : null]}
            >
              {index > 0 ? <View style={s.connector} /> : null}
              <Pressable
                style={s.node}
                onPress={() => onOpenSection(chapter.title)}
                accessibilityRole="button"
                accessibilityLabel={chapter.title}
              >
                <View
                  style={[
                    s.circle,
                    access === "done" ? s.circleDone : null,
                    access === "current" ? s.circleCurrent : null,
                    access === "locked" ? s.circleLocked : null,
                  ]}
                >
                  {access === "done" ? (
                    <Icon name="checkmark" size={26} color={theme.onPrimary} />
                  ) : access === "locked" ? (
                    <Icon name="lock-closed-outline" size={20} color={theme.textTertiary} />
                  ) : (
                    <Text style={s.initial}>{initial}</Text>
                  )}
                </View>
                <View
                  style={[
                    s.label,
                    access === "current" ? s.labelCurrent : null,
                    access === "done" ? s.labelDone : null,
                    access === "locked" ? s.labelLocked : null,
                  ]}
                >
                  <Text
                    style={[
                      s.labelText,
                      access === "locked" ? s.labelTextLocked : null,
                    ]}
                    numberOfLines={2}
                  >
                    {chapter.title}
                  </Text>
                </View>
              </Pressable>
            </View>
          );
        })}
      </View>
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
    path: { alignItems: "center", paddingVertical: 8, gap: 0 },
    nodeWrap: { alignItems: "center", width: "100%" },
    nodeOffset: { transform: [{ translateX: 56 }] },
    connector: {
      width: 3,
      height: 22,
      borderRadius: 2,
      backgroundColor: theme.border,
      marginBottom: 4,
    },
    node: { alignItems: "center", gap: 8 },
    circle: {
      width: 72,
      height: 72,
      borderRadius: 36,
      alignItems: "center",
      justifyContent: "center",
      borderWidth: 3,
    },
    circleCurrent: {
      backgroundColor: theme.primary,
      borderColor: theme.primary,
    },
    circleDone: {
      backgroundColor: theme.success,
      borderColor: theme.success,
    },
    circleLocked: {
      backgroundColor: theme.surfaceAlt,
      borderColor: theme.border,
    },
    initial: {
      fontSize: 26,
      fontWeight: "800",
      color: theme.onPrimary,
    },
    label: {
      borderRadius: 10,
      paddingHorizontal: 10,
      paddingVertical: 5,
      maxWidth: 140,
    },
    labelCurrent: { backgroundColor: theme.primaryLight },
    labelDone: { backgroundColor: theme.successLight },
    labelLocked: { backgroundColor: theme.surfaceAlt },
    labelText: {
      fontSize: 13,
      fontWeight: "700",
      color: theme.text,
      textAlign: "center",
    },
    labelTextLocked: { color: theme.textTertiary },
  });
}
