import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import {
  branchAccess,
  domainAccess,
  type DomainProgress,
} from "@/lib/projects/domainPath";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Access = "done" | "current" | "locked";

type Props = {
  domains: DomainProgress[];
  upNext?: string | null;
  onOpenChapter: (title: string) => void;
};

const NODE = 36;

export function LearningPathList({ domains, upNext, onOpenChapter }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  if (domains.length === 0) {
    return null;
  }

  const rows = domains.flatMap((domain) => {
    const domainState = domainAccess(domains, domain.title, upNext);
    const domainLocked = domainState === "locked";
    return domain.chapters.map((chapter) => ({
      chapter,
      access: branchAccess(chapter, upNext, domainLocked),
      hideDomain: domain.chapters.length === 1 && chapter.title === domain.title,
      domainTitle: domain.title,
    }));
  });

  return (
    <View style={s.list}>
      {rows.map((row, index) => {
        const { chapter, access } = row;
        const locked = access === "locked";
        const wordsLabel =
          access === "done"
            ? t("projects.group_review_meta", { count: chapter.total })
            : t("projects.chapter_words", {
                done: chapter.mastered,
                total: chapter.total,
              });
        return (
          <View key={chapter.title} style={s.rowBlock}>
            {index > 0 ? <View style={s.stem} /> : null}
            <Pressable
              style={s.row}
              onPress={() => {
                if (locked) return;
                onOpenChapter(chapter.title);
              }}
              disabled={locked}
              accessibilityRole="button"
              accessibilityState={{ disabled: locked }}
              accessibilityLabel={`${chapter.title}. ${wordsLabel}`}
            >
              <View
                style={[
                  s.node,
                  access === "done" ? s.nodeDone : null,
                  access === "current" ? s.nodeCurrent : null,
                  locked ? s.nodeLocked : null,
                ]}
              >
                {access === "done" ? (
                  <Icon name="checkmark" size={18} color={theme.onPrimary} />
                ) : locked ? (
                  <Icon name="lock-closed-outline" size={16} color={theme.textTertiary} />
                ) : (
                  <Icon name="play" size={16} color={theme.onPrimary} />
                )}
              </View>
              <View style={s.copy}>
                {!row.hideDomain ? (
                  <Text style={s.domain}>{row.domainTitle}</Text>
                ) : null}
                <Text style={[s.title, locked ? s.titleLocked : null]} numberOfLines={2}>
                  {chapter.title}
                </Text>
                <Text style={s.meta}>{wordsLabel}</Text>
              </View>
              {locked ? null : (
                <Icon name="chevron-forward" size={18} color={theme.textTertiary} />
              )}
            </Pressable>
          </View>
        );
      })}
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    list: { gap: 0 },
    rowBlock: { alignItems: "stretch" },
    stem: {
      width: 2,
      height: Space.sm,
      marginLeft: NODE / 2 - 1,
      backgroundColor: theme.border,
    },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      paddingVertical: Space.sm,
    },
    node: {
      width: NODE,
      height: NODE,
      borderRadius: NODE / 2,
      alignItems: "center",
      justifyContent: "center",
    },
    nodeCurrent: { backgroundColor: theme.primary },
    nodeDone: { backgroundColor: theme.success },
    nodeLocked: {
      backgroundColor: theme.surfaceAlt,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    copy: { flex: 1, gap: 2 },
    domain: {
      ...Type.overline,
      color: theme.textTertiary,
    },
    title: {
      ...Type.body,
      fontWeight: "700",
      color: theme.text,
    },
    titleLocked: { color: theme.textTertiary, fontWeight: "600" },
    meta: { ...Type.caption, color: theme.textSecondary },
  });
}
