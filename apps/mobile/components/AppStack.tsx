import { Stack } from "expo-router";
import { useTranslation } from "react-i18next";

import { stackBackOptions } from "@/ui/controls/StackBackButton";
import { useReduceMotion } from "@/lib/reduceMotion";
import { useStackHeaderOptions } from "@/lib/stackHeader";
import {
  stackAuthTransition,
  stackHomeTransition,
  stackPushTransition,
  stackUtilityTransition,
} from "@/lib/stackTransitions";
import { useTheme } from "@/lib/theme";

type Props = {
  /** An account is signed in (`useAuth().token`). */
  signedIn: boolean;
};

/**
 * The app's root stack. Sign-in and the account's screens are each behind a guard
 * (`Stack.Protected`): a sign-out takes every screen of the account out of the history, so
 * Back never shows the last account's chat, and a sign-in starts on one chat screen. A
 * Redirect on each screen left them in the stack, and each sign-in put another on top
 * (pre-launch review, 2026-11-27). The first screen of a group is where its guard lands.
 */
export function AppStack({ signedIn }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const header = useStackHeaderOptions();
  const reduceMotion = useReduceMotion();

  return (
    <Stack
      screenOptions={{
        ...stackPushTransition(reduceMotion),
        headerShown: false,
        contentStyle: { backgroundColor: theme.bg },
      }}
    >
      <Stack.Protected guard={!signedIn}>
        <Stack.Screen name="login" options={stackAuthTransition(reduceMotion)} />
        <Stack.Screen name="onboarding" options={stackAuthTransition(reduceMotion)} />
      </Stack.Protected>
      <Stack.Protected guard={signedIn}>
        <Stack.Screen
          name="index"
          options={{ ...stackHomeTransition(), title: "", headerShown: false }}
        />
        <Stack.Screen name="consent" options={stackAuthTransition(reduceMotion)} />
        <Stack.Screen
          name="memory"
          options={{ ...stackUtilityTransition(reduceMotion), headerShown: false }}
        />
        <Stack.Screen
          name="settings"
          options={{ ...stackPushTransition(reduceMotion), headerShown: false }}
        />
        <Stack.Screen
          name="todos"
          options={{
            ...stackUtilityTransition(reduceMotion),
            ...header,
            headerShown: true,
            title: t("drawer.reminders"),
            headerBackVisible: false,
            ...stackBackOptions(),
          }}
        />
        <Stack.Screen
          name="gallery"
          options={{
            ...stackUtilityTransition(reduceMotion),
            ...header,
            headerShown: true,
            title: t("gallery.title"),
            headerBackVisible: false,
            headerRight: undefined,
            ...stackBackOptions(),
          }}
        />
      </Stack.Protected>
    </Stack>
  );
}
