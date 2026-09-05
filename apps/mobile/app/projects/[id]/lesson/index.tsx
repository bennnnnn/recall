import { useMemo } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { LearningPathList } from "@/components/projects/LearningPathList";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAuth } from "@/contexts/AuthContext";
import { useProjectDetail } from "@/hooks/useProjectDetail";
import { openLearningLesson } from "@/lib/lessonLaunch";
import { isLanguageProject } from "@/lib/languageLevels";
import { chapterKey } from "@/lib/projects/chapterAccess";
import { branchAccess, domainAccess, groupPathByDomain } from "@/lib/projects/domainPath";
import { resolveDailyGoal } from "@/lib/projects/dailyGoals";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export default function LearningLessonMapScreen() {
  const owner = useAccountViewOwner();
  return <LessonMapContent key={owner.key} isCurrent={owner.isCurrent} />;
}

export function LessonMapContent({ isCurrent }: { isCurrent: () => boolean }) {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const projectId = typeof id === "string" ? id : undefined;
  const { project, loading, loadError, load, isCurrentOwner } = useProjectDetail(projectId);

  if (!token) return <Redirect href="/login" />;
  if (!projectId) return <Redirect href="/projects" />;

  if (loading && !project) return <SkeletonList />;

  if (!project) {
    return loadError ? (
      <StateView
        variant="error"
        title={t("projects.load_failed")}
        onRetry={() => void load({ force: true })}
        retryLabel={t("common.retry")}
      />
    ) : (
      <StateView variant="empty" title={t("projects.not_found")} />
    );
  }

  if (!isLanguageProject(project.kind)) {
    return <Redirect href="/projects" />;
  }

  const domains = groupPathByDomain(project.path_progress ?? []);
  const stats = project.stats;
  const dailyGoal = resolveDailyGoal(project.daily_goal);
  const completedToday =
    stats?.completed_today ?? (stats?.mastered_today ?? 0) + (stats?.missed_today ?? 0);
  const todayPct =
    dailyGoal > 0
      ? Math.min(100, Math.round((Math.min(completedToday, dailyGoal) / dailyGoal) * 100))
      : 0;

  const startChapter = (title: string) => {
    if (!isCurrent() || !isCurrentOwner()) return;
    const domain = domains.find((entry) =>
      entry.chapters.some((chapter) => chapterKey(chapter.title) === chapterKey(title)),
    );
    if (!domain) return;
    const chapter = domain.chapters.find((entry) => chapterKey(entry.title) === chapterKey(title));
    const locked = domainAccess(domains, domain.title, project.up_next) === "locked";
    if (!chapter || branchAccess(chapter, project.up_next, locked) === "locked") return;
    openLearningLesson(router, {
      projectId: project.id,
      chapter: chapter.title,
    });
  };

  return (
    <ScrollView style={s.root} contentContainerStyle={s.content}>
      {loadError ? (
        <StateView
          compact
          variant="error"
          title={t("projects.load_failed")}
          onRetry={() => void load({ force: true })}
        />
      ) : null}
      {project.up_next ? (
        <View style={s.nextCard}>
          <Text style={s.nextLabel}>{t("lesson.next_lesson")}</Text>
          <Text style={s.nextTitle}>{project.up_next}</Text>
          <Button
            title={t("lesson.start_practice")}
            onPress={() => startChapter(project.up_next!)}
          />
        </View>
      ) : null}
      {stats && dailyGoal > 0 ? (
        <View style={s.todayCard}>
          <Text style={s.todayLabel}>
            {completedToday >= dailyGoal
              ? t("projects.list.goal_met_today")
              : t("projects.list.today_progress", { done: completedToday, goal: dailyGoal })}
          </Text>
          <View
            style={s.todayTrack}
            accessibilityRole="progressbar"
            accessibilityValue={{
              min: 0,
              max: dailyGoal,
              now: Math.min(completedToday, dailyGoal),
            }}
          >
            <View style={[s.todayFill, { width: `${todayPct}%` }]} />
          </View>
        </View>
      ) : null}

      {domains.length === 0 ? (
        <StateView
          variant="empty"
          icon="book-outline"
          title={t("lesson.chapter_empty")}
          onRetry={() => void load({ force: true })}
        />
      ) : null}
      <LearningPathList domains={domains} upNext={project.up_next} onOpenChapter={startChapter} />
    </ScrollView>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    nextCard: {
      backgroundColor: theme.primaryLight,
      borderRadius: 20,
      padding: Space.lg,
      gap: Space.md,
      marginBottom: Space.lg,
    },
    nextLabel: { ...Type.overline, color: theme.primary },
    nextTitle: { ...Type.navTitle, color: theme.text, fontSize: 24, lineHeight: 32 },
    root: { flex: 1, backgroundColor: theme.bg },
    content: { padding: Space.lg, paddingBottom: 48 },
    todayCard: {
      marginBottom: Space.md,
      gap: 6,
    },
    todayLabel: {
      ...Type.caption,
      fontWeight: "600",
      color: theme.textSecondary,
    },
    todayTrack: {
      height: 6,
      borderRadius: 3,
      backgroundColor: theme.border,
      overflow: "hidden",
    },
    todayFill: {
      height: 6,
      borderRadius: 3,
      backgroundColor: theme.primary,
    },
  });
}
