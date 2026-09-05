import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useTranslation } from "react-i18next";
import { VocabCard } from "@/components/VocabCard";
import { StateView } from "@/components/StateView";
import type { ProjectDetail, ProjectItem } from "@/lib/api";
import { itemToCard } from "@/lib/projects/chapterLesson";
import { vocabularyGroups } from "@/lib/projects/vocabularyOverview";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Row =
  | { kind: "group"; key: string; title: string; domain?: string; count: number }
  | { kind: "word"; key: string; item: ProjectItem };

type Props = {
  project: ProjectDetail;
  query: string;
  onSpeak: (word: string) => void;
  onRetry: () => void;
};

export function VocabularyOverview({ project, query, onSpeak, onRetry }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const rows = useMemo<Row[]>(
    () =>
      vocabularyGroups(project, query).flatMap((group) => [
        {
          kind: "group" as const,
          key: `group:${group.key}`,
          title: group.title,
          domain: group.domain,
          count: group.items.length,
        },
        ...group.items.map((item) => ({
          kind: "word" as const,
          key: `word:${group.key}:${item.id}`,
          item,
        })),
      ]),
    [project, query],
  );
  const count = rows.filter((row) => row.kind === "word").length;
  return (
    <FlashList
      data={rows}
      keyExtractor={(row) => row.key}
      getItemType={(row) => row.kind}
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode="on-drag"
      contentContainerStyle={s.content}
      ListHeaderComponent={
        count ? (
          <Text style={s.total} accessibilityLiveRegion="polite">
            {t("vocabulary.entry_count", { count })}
          </Text>
        ) : null
      }
      ListEmptyComponent={
        <StateView
          variant="empty"
          icon="book-outline"
          title={t(query.trim() ? "vocabulary.no_results" : "vocabulary.empty")}
          onRetry={query.trim() ? undefined : onRetry}
        />
      }
      renderItem={({ item: row }) =>
        row.kind === "group" ? (
          <View style={s.group}>
            {row.domain && row.domain !== row.title ? (
              <Text style={s.domain}>{row.domain}</Text>
            ) : null}
            <Text style={s.groupTitle} accessibilityRole="header">
              {row.title}
            </Text>
            <Text style={s.groupCount}>{t("vocabulary.entry_count", { count: row.count })}</Text>
          </View>
        ) : (
          <View style={s.word}>
            <VocabCard
              card={itemToCard(row.item)}
              language={project.target_language}
              variant="overview"
              onSpeak={() => onSpeak(row.item.content)}
            />
          </View>
        )
      }
    />
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    content: { paddingHorizontal: Space.lg, paddingBottom: Space.xl + Space.lg },
    total: { ...Type.secondary, color: theme.textSecondary, paddingTop: Space.md },
    group: { gap: Space.xxs, paddingTop: Space.lg, paddingBottom: Space.md },
    domain: { ...Type.overline, color: theme.textSecondary },
    groupTitle: { ...Type.title, color: theme.text },
    groupCount: { ...Type.caption, color: theme.textSecondary },
    word: {
      padding: Space.md,
      marginBottom: Space.md,
      borderRadius: Radius.lg,
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
  });
}
