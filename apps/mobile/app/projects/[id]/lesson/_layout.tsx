import { Stack } from "expo-router";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { StackBackButton } from "@/components/StackBackButton";
import { stackHeaderOptions } from "@/lib/stackHeader";
import { stackPushTransition } from "@/lib/stackTransitions";
import { useTheme } from "@/lib/theme";

export default function LessonLayout() {
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
        headerLeft: () => <StackBackButton fallback="/projects" />,
      }}
    >
      <Stack.Screen name="index" options={{ title: t("lesson.lessons") }} />
      <Stack.Screen name="play" options={{ headerShown: false, title: t("lesson.open") }} />
    </Stack>
  );
}
