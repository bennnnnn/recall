import { Stack } from "expo-router";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { StackBackButton } from "@/components/StackBackButton";
import { stackHeaderOptions } from "@/lib/stackHeader";
import { useReduceMotion } from "@/lib/reduceMotion";
import { stackPushTransition } from "@/lib/stackTransitions";
import { useTheme } from "@/lib/theme";

function subScreen(
  title: string,
  header: ReturnType<typeof stackHeaderOptions>,
) {
  return {
    ...header,
    title,
    headerLeft: () => <StackBackButton icon="arrow-back" fallback="/settings" />,
  };
}

export default function SettingsLayout() {
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
        headerLeft: () => <StackBackButton icon="arrow-back" fallback="/" />,
      }}
    >
      <Stack.Screen name="index" options={{ title: t("settings.title"), headerShown: false }} />
      <Stack.Screen
        name="models"
        options={subScreen(t("settings.model"), header)}
      />
      <Stack.Screen
        name="usage"
        options={subScreen(t("settings.usage_group"), header)}
      />
      <Stack.Screen
        name="preferences"
        options={subScreen(t("settings.personalization"), header)}
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
        options={subScreen(t("settings.connected_apps"), header)}
      />
      <Stack.Screen
        name="connected-app"
        options={subScreen(t("settings.connected_apps"), header)}
      />
      <Stack.Screen
        name="data-controls"
        options={subScreen(t("settings.data_controls"), header)}
      />
      <Stack.Screen
        name="archived-chats"
        options={subScreen(t("settings.archived_chats"), header)}
      />
      <Stack.Screen
        name="security"
        options={subScreen(t("settings.security"), header)}
      />
      <Stack.Screen
        name="help"
        options={subScreen(t("settings.help"), header)}
      />
      <Stack.Screen
        name="about"
        options={subScreen(t("settings.about"), header)}
      />
    </Stack>
  );
}
