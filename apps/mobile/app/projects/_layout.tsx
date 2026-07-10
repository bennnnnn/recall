import { Stack } from "expo-router";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { StackBackButton } from "@/components/StackBackButton";
import { stackHeaderOptions } from "@/lib/stackHeader";
import { stackPushTransition } from "@/lib/stackTransitions";
import { useTheme } from "@/lib/theme";

export default function ProjectsLayout() {
  const { t } = useTranslation();
  const theme = useTheme();
  const header = useMemo(() => stackHeaderOptions(theme), [theme]);

  return (
    <Stack
      screenOptions={{
        ...stackPushTransition(),
        ...header,
        headerShown: true,
        contentStyle: { backgroundColor: theme.bg },
        headerBackVisible: false,
        headerLeft: () => <StackBackButton fallback="/" />,
      }}
    >
      <Stack.Screen name="index" options={{ title: t("projects.title") }} />
      <Stack.Screen
        name="[id]"
        options={{ ...stackPushTransition(), headerShown: false }}
      />
    </Stack>
  );
}
