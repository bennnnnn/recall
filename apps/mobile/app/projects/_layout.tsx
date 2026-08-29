import { Stack } from "expo-router";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { StackBackButton } from "@/components/StackBackButton";
import { stackHeaderOptions } from "@/lib/stackHeader";
import { useReduceMotion } from "@/lib/reduceMotion";
import { stackPushTransition } from "@/lib/stackTransitions";
import { useTheme } from "@/lib/theme";

export default function ProjectsLayout() {
  const { t } = useTranslation();
  const theme = useTheme();
  const header = useMemo(() => stackHeaderOptions(theme), [theme]);
  const reduceMotion = useReduceMotion();

  return (
    <Stack
      screenOptions={{
        ...stackPushTransition(reduceMotion),
        ...header,
        headerShown: true,
        contentStyle: { backgroundColor: theme.bg },
        headerBackVisible: false,
        headerLeft: () => <StackBackButton fallback="/" />,
      }}
    >
      <Stack.Screen name="index" options={{ title: t("projects.title") }} />
      <Stack.Screen
        name="create"
        options={{
          title: t("projects.add_learning"),
          headerLeft: () => <StackBackButton fallback="/projects" />,
        }}
      />
      <Stack.Screen
        name="[id]"
        options={{ ...stackPushTransition(reduceMotion), headerShown: false }}
      />
    </Stack>
  );
}
