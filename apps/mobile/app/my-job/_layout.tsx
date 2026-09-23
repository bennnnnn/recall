import { Stack } from "expo-router";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { StackBackButton } from "@/components/StackBackButton";
import { useReduceMotion } from "@/lib/reduceMotion";
import { stackHeaderOptions } from "@/lib/stackHeader";
import { stackPushTransition } from "@/lib/stackTransitions";
import { useTheme } from "@/lib/theme";

export default function MyJobLayout() {
  const theme = useTheme();
  const { t } = useTranslation();
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
      <Stack.Screen name="index" options={{ title: t("my_job.title") }} />
      {/* The setup wizard renders its own step-aware header. */}
      <Stack.Screen name="setup" options={{ headerShown: false }} />
      {/* Match detail renders its own company-aware header. */}
      <Stack.Screen name="match/[id]" options={{ headerShown: false }} />
    </Stack>
  );
}
