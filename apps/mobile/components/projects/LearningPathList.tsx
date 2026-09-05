import { Fragment, useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { domainIcon } from "@/lib/projects/domainIcons";
import { branchAccess, domainAccess, type DomainProgress } from "@/lib/projects/domainPath";
import { Radius } from "@/lib/radius";
import { shadowGlow, shadowRaised } from "@/lib/shadow";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  domains: DomainProgress[];
  upNext?: string | null;
  onOpenChapter: (title: string) => void;
};

const NODE = 52;

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
    return domain.chapters.map((chapter, index) => ({
      firstInDomain: index === 0,
      chapter,
      access: branchAccess(chapter, upNext, domainLocked),
      hideDomain: domain.chapters.length === 1 && chapter.title === domain.title,
      domainTitle: domain.title,
    }));
  });

  return (
    <View style={s.list}>
      {rows.map((row) => {
        const { chapter, access } = row;
        const locked = access === "locked";
        const current = access === "current";
        const done = access === "done";
        const wordsLabel =
          access === "done"
            ? t("projects.group_review_meta", { count: chapter.total })
            : t("projects.chapter_words", {
                done: chapter.mastered,
                total: chapter.total,
              });
        const progressPct =
          current && chapter.total > 0
            ? Math.min(1, Math.max(0, chapter.mastered / chapter.total))
            : 0;

        return (
          <Fragment key={chapter.title}>
            {row.firstInDomain && !row.hideDomain ? (
              <Text style={s.domainHeading} accessibilityRole="header">
                {row.domainTitle}
              </Text>
            ) : null}
            <Pressable
              style={[s.card, done || current ? shadowRaised(theme) : null]}
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
                  done ? s.nodeDone : null,
                  current ? s.nodeCurrent : null,
                  locked ? s.nodeLocked : null,
                  current ? shadowGlow(theme, theme.primary) : null,
                ]}
              >
                <Icon
                  name={done ? "checkmark" : domainIcon(row.domainTitle)}
                  size={done ? 22 : 24}
                  color={locked ? theme.textTertiary : theme.onPrimary}
                />
                {locked ? (
                  <View style={s.lockBadge}>
                    <Icon name="lock-closed-outline" size={11} color={theme.textTertiary} />
                  </View>
                ) : null}
              </View>

              <View style={s.copy}>
                <Text style={[s.title, locked ? s.titleLocked : null]} numberOfLines={2}>
                  {chapter.title}
                </Text>
                <Text style={[s.meta, locked ? null : s.metaActive]}>{wordsLabel}</Text>
                {current ? (
                  <View style={s.progressTrack}>
                    <View style={[s.progressFill, { width: `${progressPct * 100}%` }]} />
                  </View>
                ) : null}
              </View>

              {locked ? null : <Icon name="chevron-forward" size={18} color={theme.textTertiary} />}
            </Pressable>
          </Fragment>
        );
      })}
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    domainHeading: {
      ...Type.navTitle,
      color: theme.text,
      marginTop: Space.lg,
      marginBottom: Space.sm,
    },
    list: { gap: Space.sm },
    card: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      padding: Space.md,
      borderRadius: Radius.lg,
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
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
    lockBadge: {
      position: "absolute",
      bottom: -3,
      right: -3,
      width: 20,
      height: 20,
      borderRadius: 10,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    copy: { flex: 1, gap: 3 },
    domain: {
      ...Type.overline,
      color: theme.textTertiary,
    },
    title: {
      ...Type.body,
      fontSize: 17,
      fontWeight: "700",
      color: theme.text,
    },
    titleLocked: { color: theme.textTertiary, fontWeight: "600" },
    meta: { ...Type.caption, color: theme.textTertiary, fontWeight: "500" },
    metaActive: { color: theme.textSecondary },
    progressTrack: {
      height: 4,
      borderRadius: Radius.full,
      backgroundColor: theme.border,
      overflow: "hidden",
      marginTop: 2,
    },
    progressFill: {
      height: "100%",
      borderRadius: Radius.full,
      backgroundColor: theme.primary,
    },
  });
}
