import { Stack } from "expo-router";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { StackBackButton } from "@/components/StackBackButton";
import { stackHeaderOptions } from "@/lib/stackHeader";
import { useTheme } from "@/lib/theme";

export default function ProjectIdLayout() {
  const { t } = useTranslation();
  const theme = useTheme();
  const header = useMemo(() => stackHeaderOptions(theme), [theme]);

  return (
    <Stack
      screenOptions={{
        ...header,
        headerShown: true,
        contentStyle: { backgroundColor: theme.bg },
        headerBackVisible: false,
        headerLeft: () => <StackBackButton fallback="/projects" />,
      }}
    >
      <Stack.Screen name="index" options={{ title: t("projects.detail") }} />
    </Stack>
  );
}
