import { useCallback, useMemo, useState } from "react";
import { RefreshControl, StyleSheet, View } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { AddFab } from "@/ui/controls/AddFab";
import { LearningProjectCard } from "@/features/learning/components/LearningProjectCard";
import { SkeletonList } from "@/ui/feedback/SkeletonLoader";
import { StateView } from "@/ui/feedback/StateView";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useAuth } from "@/contexts/AuthContext";
import { useProjects } from "@/features/learning/context/ProjectsContext";
import { isLanguageProject } from "@/features/learning/model/languageLevels";
import type { IconName } from "@/ui/icons/names";
import { formatDailyGoalShort, resolveDailyGoal } from "@/features/learning/model/dailyGoals";
import { lessonMapPath } from "@/features/learning/model/chapterAccess";
import { canAddLearningProject } from "@/features/learning/model/projectCreateFlow";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";

function kindIcon(kind: string): IconName {
  if (isLanguageProject(kind)) return "languages";
  return "folder";
}

export default function ProjectsScreen() {
  const owner = useAccountViewOwner();
  return <ProjectsContent key={owner.key} isCurrent={owner.isCurrent} />;
}
function ProjectsContent({ isCurrent }: { isCurrent: () => boolean }) {
  const { token } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const router = useRouter();
  const { projects, loading, error, refresh } = useProjects();
  const visibleProjects = useMemo(() => projects.filter((p) => !p.archived), [projects]);
  const showAddLearning = useMemo(() => canAddLearningProject(projects), [projects]);
  const [pullRefreshing, setPullRefreshing] = useState(false);

  useFocusEffect(
    useCallback(() => {
      // List cards come from GET /projects. Do not also pull /home or every
      // class detail — those load when the user opens Home or a class.
      void refresh({ silent: true });
    }, [refresh]),
  );

  const openCreate = useCallback(() => {
    if (isCurrent()) router.push("/projects/create");
  }, [router, isCurrent]);

  const openProject = useCallback(
    (projectId: string) => {
      if (isCurrent()) router.push(lessonMapPath(projectId));
    },
    [router, isCurrent],
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
                if (!isCurrent()) return;
                setPullRefreshing(true);
                await refresh({ silent: true, force: true });
                if (isCurrent()) setPullRefreshing(false);
              }}
              tintColor={C.primary}
            />
          }
          ListHeaderComponent={
            <>
              {!error && visibleProjects.length === 0 ? (
                <StateView variant="empty" icon="book" title={t("projects.empty_title")} />
              ) : null}
              {error ? (
                <StateView
                  variant="error"
                  title={t("common.error")}
                  onRetry={() => {
                    if (isCurrent()) void refresh({ force: true });
                  }}
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
                dailyLabel={dailyValue}
                onOpen={openProject}
              />
            );
          }}
        />
      )}

      {showAddLearning ? (
        <AddFab onPress={openCreate} accessibilityLabel={t("projects.add_learning_a11y")} />
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
