import { useMemo } from "react";
import { ScrollView, StyleSheet } from "react-native";
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { LearningPathList } from "@/components/projects/LearningPathList";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAuth } from "@/contexts/AuthContext";
import { useProjectDetail } from "@/hooks/useProjectDetail";
import { invalidateProjectDetail } from "@/lib/cache/projectDetailCache";
import { openLearningLesson } from "@/lib/lessonLaunch";
import { isLanguageProject } from "@/lib/languageLevels";
import { chapterAccess, chapterKey } from "@/lib/projects/chapterAccess";
import { buildChapterLessonPrompt } from "@/lib/projects/projectChat";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";

export default function LearningLessonMapScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const projectId = typeof id === "string" ? id : undefined;
  const { project, loading, loadError, load } = useProjectDetail(projectId);

  if (!token) return <Redirect href="/login" />;
  if (!projectId) return <Redirect href="/projects" />;

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

  if (!isLanguageProject(project.kind)) {
    return <Redirect href={`/projects/${project.id}`} />;
  }

  const pathProgress = project.path_progress ?? [];

  const startChapter = (title: string) => {
    const chapter = pathProgress.find((entry) => chapterKey(entry.title) === chapterKey(title));
    if (!chapter || chapterAccess(chapter, project.up_next) === "locked") return;
    invalidateProjectDetail(project.id);
    openLearningLesson(router, {
      projectId: project.id,
      prompt: buildChapterLessonPrompt(project, chapter.title),
      quizLanguage: project.target_language,
      quizVariant: "vocab",
    });
  };

  return (
    <ScrollView style={s.root} contentContainerStyle={s.content}>
      <LearningPathList
        pathProgress={pathProgress}
        upNext={project.up_next}
        onOpenSection={startChapter}
      />
    </ScrollView>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: theme.bg },
    content: { padding: Space.lg, paddingBottom: 48 },
  });
}
