import { Stack } from "expo-router";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { StackBackButton } from "@/components/StackBackButton";
import { Radius } from "@/lib/radius";
import { stackHeaderOptions } from "@/lib/stackHeader";
import { useReduceMotion } from "@/lib/reduceMotion";
import { stackPushTransition } from "@/lib/stackTransitions";
import { useTheme } from "@/lib/theme";

export default function AutomationsLayout() {
  const { t } = useTranslation();
  const theme = useTheme();
  const header = useMemo(() => stackHeaderOptions(theme), [theme]);
  const reduceMotion = useReduceMotion();
  const headerButtonStyle = useMemo(
    () => ({ backgroundColor: theme.surface, borderRadius: Radius.full }),
    [theme.surface],
  );

  return (
    <Stack
      screenOptions={{
        ...stackPushTransition(reduceMotion),
        ...header,
        headerShown: true,
        contentStyle: { backgroundColor: theme.bg },
        headerBackVisible: false,
        headerLeft: () => <StackBackButton fallback="/" style={headerButtonStyle} />,
      }}
    >
      <Stack.Screen name="index" options={{ title: t("automations.title") }} />
      <Stack.Screen
        name="[id]"
        options={{
          title: "",
          headerLeft: () => (
            <StackBackButton fallback="/automations" icon="close" style={headerButtonStyle} />
          ),
        }}
      />
    </Stack>
  );
}
