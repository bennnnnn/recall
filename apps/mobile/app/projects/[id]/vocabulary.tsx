import { useMemo, useState } from "react";
import { Pressable, StyleSheet, TextInput, View } from "react-native";
import { Redirect, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { VocabularyOverview } from "@/components/projects/VocabularyOverview";
import { Icon } from "@/components/Icon";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAuth } from "@/contexts/AuthContext";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useLessonAudio } from "@/hooks/useLessonAudio";
import { useProjectDetail } from "@/hooks/useProjectDetail";
import { isLanguageProject } from "@/lib/languageLevels";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export default function VocabularyScreen() {
  const owner = useAccountViewOwner();
  return <VocabularyContent key={owner.key} isCurrent={owner.isCurrent} />;
}

export function VocabularyContent({ isCurrent }: { isCurrent: () => boolean }) {
  const { token } = useAuth();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [query, setQuery] = useState("");
  const { project, loading, loadError, load, isCurrentOwner } = useProjectDetail(
    typeof id === "string" ? id : undefined,
  );
  const audio = useLessonAudio(isCurrent);
  if (!token) return <Redirect href="/login" />;
  if (typeof id !== "string") return <Redirect href="/projects" />;
  const retry = () => {
    if (isCurrent() && isCurrentOwner()) void load({ force: true });
  };
  if (loading && !project) return <SkeletonList />;
  if (!project)
    return (
      <StateView
        variant={loadError ? "error" : "empty"}
        title={t(loadError ? "projects.load_failed" : "projects.not_found")}
        onRetry={retry}
      />
    );
  if (!isLanguageProject(project.kind)) return <Redirect href="/projects" />;
  return (
    <View style={s.root}>
      <View style={s.search}>
        <Icon name="search-outline" size={20} color={theme.textSecondary} />
        <TextInput
          style={s.input}
          value={query}
          onChangeText={(value) => {
            if (isCurrent()) setQuery(value);
          }}
          placeholder={t("vocabulary.search")}
          accessibilityLabel={t("vocabulary.search")}
          placeholderTextColor={theme.textTertiary}
          autoCapitalize="none"
          autoCorrect={false}
          returnKeyType="search"
        />
        {query ? (
          <Pressable
            style={s.clear}
            onPress={() => {
              if (isCurrent()) setQuery("");
            }}
            accessibilityRole="button"
            accessibilityLabel={t("vocabulary.clear_search")}
          >
            <Icon name="close-circle" size={22} color={theme.textSecondary} />
          </Pressable>
        ) : null}
      </View>
      {loadError ? (
        <StateView compact variant="error" title={t("projects.load_failed")} onRetry={retry} />
      ) : null}
      <VocabularyOverview
        project={project}
        query={query}
        onRetry={retry}
        onSpeak={(word) => {
          if (isCurrent() && isCurrentOwner()) void audio.start(word, project.target_language);
        }}
      />
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: theme.bg },
    search: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      marginHorizontal: Space.lg,
      marginTop: Space.md,
      paddingHorizontal: Space.md,
      minHeight: Space.minTouch,
      borderRadius: Radius.md,
      backgroundColor: theme.surfaceAlt,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    input: { ...Type.body, flex: 1, color: theme.text, paddingVertical: Space.sm },
    clear: {
      minHeight: Space.minTouch,
      minWidth: Space.minTouch,
      alignItems: "center",
      justifyContent: "center",
    },
  });
}
