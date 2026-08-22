import { useMemo, useState, type ReactNode } from "react";
import { LayoutAnimation, Pressable, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";
import { useTranslation } from "react-i18next";

import { chapterKey } from "@/lib/projects/chapterAccess";
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

export function LearningPathList({ domains, upNext, onOpenChapter }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const currentDomain =
    domains.find((domain) => domainAccess(domains, domain.title, upNext) === "current")?.title ??
    null;
  const [expanded, setExpanded] = useState<string | null>(null);
  const openTitle = expanded ?? currentDomain;

  if (domains.length === 0) {
    return null;
  }

  const toggleDomain = (title: string, isLocked: boolean) => {
    if (isLocked) return;
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setExpanded((prev) => (prev === title ? "" : title));
  };

  return (
    <View style={s.list}>
      {domains.map((domain) => {
        const access = domainAccess(domains, domain.title, upNext);
        const locked = access === "locked";
        const open = !locked && chapterKey(openTitle ?? "") === chapterKey(domain.title);
        return (
          <View key={domain.title} style={s.group}>
            <PathRow
              title={domain.title}
              access={access}
              trailing={
                locked ? null : (
                  <Icon
                    name={open ? "chevron-down" : "chevron-forward"}
                    size={18}
                    color={theme.textTertiary}
                  />
                )
              }
              onPress={() => toggleDomain(domain.title, locked)}
              styles={s}
              wordsLabel={t("projects.chapter_words", {
                done: domain.mastered,
                total: domain.total,
              })}
            />
            {open
              ? domain.chapters.map((chapter) => {
                  const chapterAccessState = branchAccess(chapter, upNext, locked);
                  return (
                    <View key={chapter.title} style={s.child}>
                      <PathRow
                        title={chapter.title}
                        access={chapterAccessState}
                        trailing={
                          chapterAccessState === "locked" ? null : (
                            <Icon name="chevron-forward" size={18} color={theme.textTertiary} />
                          )
                        }
                        onPress={() => {
                          if (chapterAccessState === "locked") return;
                          onOpenChapter(chapter.title);
                        }}
                        styles={s}
                        wordsLabel={t("projects.chapter_words", {
                          done: chapter.mastered,
                          total: chapter.total,
                        })}
                      />
                    </View>
                  );
                })
              : null}
          </View>
        );
      })}
    </View>
  );
}

function PathRow({
  title,
  access,
  trailing,
  onPress,
  styles: s,
  wordsLabel,
}: {
  title: string;
  access: Access;
  trailing: ReactNode;
  onPress: () => void;
  styles: ReturnType<typeof makeStyles>;
  wordsLabel: string;
}) {
  const theme = useTheme();
  const locked = access === "locked";
  const initial = title.trim().charAt(0).toUpperCase() || "•";
  return (
    <Pressable
      style={s.row}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ disabled: locked }}
      accessibilityLabel={title}
    >
      <View
        style={[
          s.badge,
          access === "done" ? s.badgeDone : null,
          access === "current" ? s.badgeCurrent : null,
          locked ? s.badgeLocked : null,
        ]}
      >
        {access === "done" ? (
          <Icon name="checkmark" size={20} color={theme.onPrimary} />
        ) : locked ? (
          <Icon name="lock-closed-outline" size={16} color={theme.textTertiary} />
        ) : (
          <Text style={s.initial}>{initial}</Text>
        )}
      </View>
      <View style={s.copy}>
        <Text style={[s.title, locked ? s.titleLocked : null]} numberOfLines={1}>
          {title}
        </Text>
        <Text style={s.words}>{wordsLabel}</Text>
      </View>
      {trailing}
    </Pressable>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    list: { gap: Space.md },
    group: { gap: Space.sm },
    child: { paddingLeft: Space.lg },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.md,
      paddingVertical: 14,
      paddingHorizontal: 14,
      borderRadius: 12,
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    badge: {
      width: 40,
      height: 40,
      borderRadius: 20,
      alignItems: "center",
      justifyContent: "center",
    },
    badgeCurrent: { backgroundColor: theme.primary },
    badgeDone: { backgroundColor: theme.success },
    badgeLocked: { backgroundColor: theme.surfaceAlt },
    initial: { fontSize: 16, fontWeight: "800", color: theme.onPrimary },
    copy: { flex: 1, gap: 2 },
    title: { ...Type.body, fontWeight: "700", color: theme.text },
    titleLocked: { color: theme.textTertiary },
    words: { ...Type.caption, color: theme.textSecondary },
  });
}
