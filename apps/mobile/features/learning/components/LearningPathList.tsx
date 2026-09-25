import { memo, useEffect, useMemo, useState, type ReactElement } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import { LearningPathNode } from "@/features/learning/components/LearningPathNode";
import {
  branchAccess,
  domainAccess,
  type DomainProgress,
} from "@/features/learning/model/domainPath";
import type { ChapterAccess } from "@/features/learning/model/chapterAccess";
import { acknowledgeMapUnlocks, syncMapUnlocks } from "@/features/learning/model/mapUnlock";
import { Radius } from "@/lib/radius";
import { shadowRaised } from "@/lib/shadow";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type ChapterRow = {
  kind: "chapter";
  chapter: DomainProgress["chapters"][number];
  access: ChapterAccess;
  domainTitle: string;
};

type LessonMapRow = { kind: "domain"; title: string } | ChapterRow;

type Props = {
  domains: DomainProgress[];
  projectId?: string;
  upNext?: string | null;
  onOpenChapter: (title: string) => void;
  /** Screen chrome above the map (today card, overflow menu, inline error). */
  header?: ReactElement;
  /** Shown when the project has no chapters yet. */
  empty?: ReactElement;
};

const DomainHeader = memo(function DomainHeader({ title }: { title: string }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <Text style={s.domainHeading} accessibilityRole="header">
      {title}
    </Text>
  );
});

const ChapterCard = memo(function ChapterCard({
  row,
  justCompleted,
  onOpenChapter,
}: {
  row: ChapterRow;
  justCompleted: boolean;
  onOpenChapter: (title: string) => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
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
        justCompleted={justCompleted}
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
  );
});

export function LearningPathList({
  domains,
  projectId,
  upNext,
  onOpenChapter,
  header,
  empty,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [unlocked, setUnlocked] = useState<ReadonlySet<string>>(() => new Set());

  const rows = useMemo<LessonMapRow[]>(
    () =>
      domains.flatMap((domain) => {
        const domainState = domainAccess(domains, domain.title, upNext);
        const domainLocked = domainState === "locked";
        const hideDomain =
          domain.chapters.length === 1 && domain.chapters[0]?.title === domain.title;
        const chapterRows: LessonMapRow[] = domain.chapters.map((chapter) => ({
          kind: "chapter",
          chapter,
          access: branchAccess(chapter, upNext, domainLocked),
          domainTitle: domain.title,
        }));
        return hideDomain
          ? chapterRows
          : [{ kind: "domain", title: domain.title } as LessonMapRow, ...chapterRows];
      }),
    [domains, upNext],
  );

  const stickyHeaderIndices = useMemo(
    () => rows.flatMap((row, index) => (row.kind === "domain" ? [index] : [])),
    [rows],
  );

  const doneTitles = useMemo(
    () =>
      rows.flatMap((row) =>
        row.kind === "chapter" && row.access === "done" ? [row.chapter.title] : [],
      ),
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

  return (
    <FlashList
      data={rows}
      keyExtractor={(row) => (row.kind === "domain" ? `domain-${row.title}` : row.chapter.title)}
      getItemType={(row) => row.kind}
      stickyHeaderIndices={stickyHeaderIndices}
      style={s.list}
      contentContainerStyle={s.content}
      ListHeaderComponent={header}
      ListEmptyComponent={empty}
      renderItem={({ item }) =>
        item.kind === "domain" ? (
          <DomainHeader title={item.title} />
        ) : (
          <ChapterCard
            row={item}
            justCompleted={item.access === "done" && unlocked.has(item.chapter.title)}
            onOpenChapter={onOpenChapter}
          />
        )
      }
    />
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    domainHeading: {
      ...Type.navTitle,
      color: theme.text,
      paddingTop: Space.lg,
      paddingBottom: Space.sm,
      // Sticky headers scroll over chapter cards — must be opaque.
      backgroundColor: theme.bg,
    },
    list: { flex: 1, backgroundColor: theme.bg },
    content: { padding: Space.lg, paddingBottom: 48 },
    card: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      padding: Space.md,
      marginBottom: Space.sm,
      borderRadius: Radius.lg,
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    copy: { flex: 1, gap: 3 },
    title: {
      ...Type.h3,
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
