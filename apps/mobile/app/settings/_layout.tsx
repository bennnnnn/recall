import { Stack } from "expo-router";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { StackBackButton } from "@/components/StackBackButton";
import { stackHeaderOptions } from "@/lib/stackHeader";
import { stackPushTransition } from "@/lib/stackTransitions";
import { useTheme } from "@/lib/theme";

function subScreen(
  title: string,
  header: ReturnType<typeof stackHeaderOptions>,
) {
  return {
    ...header,
    title,
    headerLeft: () => <StackBackButton fallback="/settings" />,
  };
}

export default function SettingsLayout() {
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
      <Stack.Screen name="index" options={{ title: t("settings.title") }} />
      <Stack.Screen
        name="models"
        options={subScreen(t("settings.model"), header)}
      />
      <Stack.Screen
        name="preferences"
        options={subScreen(t("settings.personalization"), header)}
      />
      <Stack.Screen
        name="learning"
        options={subScreen(t("settings.learning.title"), header)}
      />
      <Stack.Screen
        name="memory-settings"
        options={subScreen(t("settings.memory"), header)}
      />
      <Stack.Screen
        name="notifications"
        options={subScreen(t("settings.notifications"), header)}
      />
      <Stack.Screen
        name="integrations"
        options={subScreen(t("settings.integrations"), header)}
      />
      <Stack.Screen
        name="data-controls"
        options={subScreen(t("settings.data_controls"), header)}
      />
      <Stack.Screen
        name="about"
        options={subScreen(t("settings.about"), header)}
      />
    </Stack>
  );
}
