import { useCallback, useMemo, useState } from "react";
import { RefreshControl, StyleSheet, View } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { AddFab } from "@/components/AddFab";
import { LearningProjectCard } from "@/components/projects/LearningProjectCard";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAuth } from "@/contexts/AuthContext";
import { useProjects } from "@/contexts/ProjectsContext";
import { type IoniconName } from "@/lib/icons";
import { levelLabelT } from "@/lib/languageLevels";
import {
  formatDailyGoalShort,
  resolveDailyGoal,
} from "@/lib/projects/dailyGoals";
import { lessonMapPath } from "@/lib/projects/chapterAccess";
import { canAddLearningProject } from "@/lib/projects/projectCreateFlow";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";

function kindIcon(kind: string): IoniconName {
  if (kind === "language" || kind === "vocabulary") return "language-outline";
  return "folder-outline";
}

export default function ProjectsScreen() {
  const { token } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const router = useRouter();
  const { projects, loading, error, refresh } = useProjects();
  const visibleProjects = useMemo(
    () => projects.filter((p) => !p.archived),
    [projects],
  );
  const showAddLearning = useMemo(
    () => canAddLearningProject(projects),
    [projects],
  );
  const [pullRefreshing, setPullRefreshing] = useState(false);

  useFocusEffect(
    useCallback(() => {
      // List cards come from GET /projects. Do not also pull /home or every
      // class detail — those load when the user opens Home or a class.
      void refresh({ silent: true });
    }, [refresh]),
  );

  const openCreate = useCallback(() => {
    router.push("/projects/create");
  }, [router]);

  const openProject = useCallback(
    (projectId: string) => {
      router.push(lessonMapPath(projectId));
    },
    [router],
  );

  if (!token) return <Redirect href="/login" />;

  return (
    <View style={s.root}>
      {loading && visibleProjects.length === 0 && !error ? (
        <SkeletonList />
      ) : (
        <FlashList
          data={visibleProjects}
          keyExtractor={(project) => project.id}
          contentContainerStyle={s.content}
          keyboardShouldPersistTaps="handled"
          ItemSeparatorComponent={() => <View style={s.listGap} />}
          refreshControl={
            <RefreshControl
              refreshing={pullRefreshing}
              onRefresh={async () => {
                setPullRefreshing(true);
                await refresh({ silent: true, force: true });
                setPullRefreshing(false);
              }}
              tintColor={C.primary}
            />
          }
          ListHeaderComponent={
            <>
              {!error && visibleProjects.length === 0 ? (
                <StateView
                  variant="empty"
                  icon="book-outline"
                  title={t("projects.empty_title")}
                />
              ) : null}
              {error ? (
                <StateView
                  variant="error"
                  title={t("common.error")}
                  onRetry={() => void refresh()}
                  retryLabel={t("common.retry")}
                />
              ) : null}
            </>
          }
          renderItem={({ item: project }) => {
            const dailyValue = formatDailyGoalShort(resolveDailyGoal(project.daily_goal));
            return (
              <LearningProjectCard
                project={project}
                icon={kindIcon(project.kind)}
                levelLabel={levelLabelT(project.level, t)}
                dailyLabel={dailyValue}
                onOpen={openProject}
              />
            );
          }}
        />
      )}

      {showAddLearning ? (
        <AddFab
          onPress={openCreate}
          accessibilityLabel={t("projects.add_learning_a11y")}
        />
      ) : null}
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: C.bg },
    content: { padding: Space.md, paddingBottom: 96 },
    listGap: { height: Space.sm },
  });
}
