import { Fragment, useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { LearningPathNode } from "@/components/projects/LearningPathNode";
import { branchAccess, domainAccess, type DomainProgress } from "@/lib/projects/domainPath";
import { acknowledgeMapUnlocks, syncMapUnlocks } from "@/lib/projects/mapUnlock";
import { Radius } from "@/lib/radius";
import { shadowRaised } from "@/lib/shadow";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  domains: DomainProgress[];
  projectId?: string;
  upNext?: string | null;
  onOpenChapter: (title: string) => void;
};

export function LearningPathList({ domains, projectId, upNext, onOpenChapter }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [unlocked, setUnlocked] = useState<ReadonlySet<string>>(() => new Set());

  const rows = useMemo(
    () =>
      domains.flatMap((domain) => {
        const domainState = domainAccess(domains, domain.title, upNext);
        const domainLocked = domainState === "locked";
        return domain.chapters.map((chapter, index) => ({
          firstInDomain: index === 0,
          chapter,
          access: branchAccess(chapter, upNext, domainLocked),
          hideDomain: domain.chapters.length === 1 && chapter.title === domain.title,
          domainTitle: domain.title,
        }));
      }),
    [domains, upNext],
  );

  const doneTitles = useMemo(
    () => rows.filter((row) => row.access === "done").map((row) => row.chapter.title),
    [rows],
  );
  const doneKey = doneTitles.join("\0");

  useEffect(() => {
    if (!projectId) return;
    const fresh = syncMapUnlocks(projectId, doneTitles);
    if (fresh.length === 0) return;
    setUnlocked((prev) => {
      const next = new Set(prev);
      let changed = false;
      for (const title of fresh) {
        if (!next.has(title)) {
          next.add(title);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
    acknowledgeMapUnlocks(projectId, fresh);
  }, [doneKey, doneTitles, projectId]);

  if (domains.length === 0) {
    return null;
  }

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
              <LearningPathNode
                access={access}
                domainTitle={row.domainTitle}
                justCompleted={done && unlocked.has(chapter.title)}
              />

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
    copy: { flex: 1, gap: 3 },
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
