import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Alert, ScrollView, StyleSheet, Text } from "react-native";
import { Redirect, useLocalSearchParams, useNavigation, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { ProjectItemRow } from "@/components/ProjectItemRow";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { LearningContinueCta } from "@/components/projects/LearningContinueCta";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAuth } from "@/contexts/AuthContext";
import { useProjectActions } from "@/hooks/useProjectActions";
import { useProjectDetail } from "@/hooks/useProjectDetail";
import type { VocabStatus } from "@/lib/api";
import { invalidateProjectDetail } from "@/lib/cache/projectDetailCache";
import { speechLocale } from "@/lib/i18n/languages";
import { chapterAccess, chapterKey } from "@/lib/projects/chapterAccess";
import { buildChapterLessonPrompt } from "@/lib/projects/projectChat";
import { openLearningLesson } from "@/lib/lessonLaunch";
import { isLanguageProject } from "@/lib/languageLevels";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

function decodeChapter(raw: string | undefined): string {
  if (!raw) return "";
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}

export default function LearningSectionScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const router = useRouter();
  const navigation = useNavigation();
  const { id, chapter: chapterParam } = useLocalSearchParams<{
    id: string;
    chapter: string;
  }>();
  const projectId = typeof id === "string" ? id : undefined;
  const chapterTitle = decodeChapter(typeof chapterParam === "string" ? chapterParam : undefined);
  const { project, loading, loadError, load } = useProjectDetail(projectId);
  const { updateProjectItem } = useProjectActions();
  const feedback = useActionFeedbackOptional();
  const [busyId, setBusyId] = useState<string | null>(null);
  const busyRef = useRef<string | null>(null);

  useLayoutEffect(() => {
    navigation.setOptions({ title: chapterTitle || t("projects.chapters_title") });
  }, [chapterTitle, navigation, t]);

  const handleItemStatusChange = useCallback(
    async (itemId: string, status: VocabStatus) => {
      if (!token || !projectId || busyRef.current) return;
      busyRef.current = itemId;
      setBusyId(itemId);
      try {
        await updateProjectItem(projectId, itemId, status);
        await load({ silent: true, force: true });
      } catch {
        if (feedback) feedback.error(t("projects.status_update_failed"));
        else Alert.alert(t("common.error"), t("projects.status_update_failed"));
      } finally {
        busyRef.current = null;
        setBusyId(null);
      }
    },
    [feedback, load, projectId, t, token, updateProjectItem],
  );

  if (!token) return <Redirect href="/login" />;

  if (loading && !project) return <SkeletonList />;

  if (!project) {
    return loadError ? (
      <StateView
        variant="error"
        title={t("projects.load_failed")}
        onRetry={() => void load()}
        retryLabel={t("common.retry")}
      />
    ) : (
      <StateView variant="empty" title={t("projects.not_found")} />
    );
  }

  if (!isLanguageProject(project.kind) || !chapterTitle) {
    return <Redirect href={`/projects/${project.id}`} />;
  }

  const chapter = (project.path_progress ?? []).find(
    (entry) => chapterKey(entry.title) === chapterKey(chapterTitle),
  );
  const words =
    project.lists.find((group) => chapterKey(group.list_title) === chapterKey(chapterTitle))
      ?.items ?? [];
  const access = chapter ? chapterAccess(chapter, project.up_next) : "locked";
  const locked = access === "locked";

  const ctaLabel =
    access === "done"
      ? t("projects.section.review")
      : words.length === 0
        ? t("projects.section.start")
        : t("projects.section.continue");

  const startLesson = () => {
    invalidateProjectDetail(project.id);
    openLearningLesson(router, {
      projectId: project.id,
      prompt: buildChapterLessonPrompt(project, chapter?.title ?? chapterTitle),
      quizLanguage: project.target_language,
      quizVariant: "vocab",
    });
  };

  return (
    <ScrollView style={s.root} contentContainerStyle={s.content}>
      <Text style={s.title}>{chapter?.title ?? chapterTitle}</Text>
      {chapter ? (
        <Text style={s.meta}>
          {t("projects.journey_topic_progress", {
            mastered: chapter.mastered,
            total: chapter.total,
          })}
        </Text>
      ) : null}
      {locked ? <Text style={s.locked}>{t("projects.section.locked")}</Text> : null}
      {!locked ? <LearningContinueCta label={ctaLabel} onPress={startLesson} /> : null}

      <Text style={s.heading}>
        {t("projects.section.words", { count: words.length })}
      </Text>
      {words.map((item) => (
        <ProjectItemRow
          key={item.id}
          item={item}
          showSpeech
          speechLanguage={speechLocale(project.target_language)}
          busy={busyId === item.id}
          onStatusChange={handleItemStatusChange}
        />
      ))}
    </ScrollView>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: theme.bg },
    content: { padding: Space.lg, gap: Space.md, paddingBottom: 48 },
    title: { ...Type.title, color: theme.text },
    meta: { fontSize: 15, fontWeight: "600", color: theme.textSecondary },
    locked: { fontSize: 15, lineHeight: 21, color: theme.textSecondary },
    heading: {
      fontSize: 13,
      fontWeight: "700",
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
      marginTop: Space.sm,
    },
  });
}
