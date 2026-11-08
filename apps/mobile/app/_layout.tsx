import "@/lib/i18n";

import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { StyleSheet } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useTranslation } from "react-i18next";

import { AuthProvider } from "@/contexts/AuthContext";
import { AiConsentRedirect } from "@/features/auth/components/AiConsentRedirect";
import { OpenedDocumentBootstrap } from "@/features/chat/components/OpenedDocumentBootstrap";
import { ActionFeedbackProvider } from "@/contexts/ActionFeedbackContext";
import { AppearanceProvider } from "@/contexts/AppearanceContext";
import { ModelsProvider } from "@/contexts/ModelsContext";
import { NetworkProvider, useNetwork } from "@/contexts/NetworkContext";
import { TodosProvider } from "@/features/todos/context/TodosContext";
import { PushNotificationBootstrap } from "@/features/todos/components/PushNotificationBootstrap";
import { OfflineBanner } from "@/components/OfflineBanner";
import { stackBackOptions } from "@/ui/controls/StackBackButton";
import { DialogHost } from "@/ui/overlay/DialogHost";
import { preloadSimulationSizing } from "@/components/rich/LazyHeavyRich";
import { useLaunchFonts } from "@/hooks/useLaunchFonts";
import { sweepOldPickerCopies } from "@/lib/accountFiles";
import { watchPhoneClock } from "@/lib/datetime/phoneClockSync";
import { boundImageMemoryCache } from "@/lib/images/memoryCache";
import { restoreLaunchPrefs } from "@/lib/launchPrefs";
import { markLaunchReady } from "@/lib/launchSplash";
import { LaunchReveal } from "@/components/LaunchReveal";
import { useReduceMotion } from "@/lib/reduceMotion";
import { scheduleIdleTask } from "@/lib/scheduleIdle";
import { useStackHeaderOptions } from "@/lib/stackHeader";
import {
  stackAuthTransition,
  stackHomeTransition,
  stackPushTransition,
  stackUtilityTransition,
} from "@/lib/stackTransitions";
import { subscribeUnknownLatexCommands } from "@/lib/math/latexNames";
import { initMobileSentry, reportUnknownLatexCommandName } from "@/lib/sentry";
import { useTheme } from "@/lib/theme";

// Before the first render: the user's appearance, accent and language.
void restoreLaunchPrefs().then(() => markLaunchReady("prefs"));
// Before anything can be picked, so a fresh pick is never in the listing.
void sweepOldPickerCopies();
// Before the first picture decodes: the memory cache keeps what it decodes until told a limit.
boundImageMemoryCache();

const markSessionRestored = () => markLaunchReady("session");

function RootNavigator() {
  const { t } = useTranslation();
  const theme = useTheme();
  const header = useStackHeaderOptions();
  const { status } = useNetwork();
  const reduceMotion = useReduceMotion();

  return (
    <>
      <StatusBar style={theme.isDark ? "light" : "dark"} />
      <OfflineBanner status={status} />
      <Stack
        screenOptions={{
          ...stackPushTransition(reduceMotion),
          headerShown: false,
          contentStyle: { backgroundColor: theme.bg },
        }}
      >
        <Stack.Screen name="login" options={stackAuthTransition(reduceMotion)} />
        <Stack.Screen name="onboarding" options={stackAuthTransition(reduceMotion)} />
        <Stack.Screen name="consent" options={stackAuthTransition(reduceMotion)} />
        <Stack.Screen
          name="index"
          options={{ ...stackHomeTransition(), title: "", headerShown: false }}
        />
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
      </Stack>
    </>
  );
}

export default function RootLayout() {
  const fontsReady = useLaunchFonts();

  // Dates follow the phone's zone and 12/24-hour setting as they change.
  useEffect(() => watchPhoneClock(), []);

  // A LaTeX command a reply used that the renderer has no entry for: reported by name.
  useEffect(() => subscribeUnknownLatexCommands(reportUnknownLatexCommandName), []);

  // Work for later in the session, once the launch has settled.
  useEffect(() => {
    return scheduleIdleTask(() => {
      void initMobileSentry();
      preloadSimulationSizing();
    });
  }, []);

  return (
    <GestureHandlerRootView style={styles.root}>
      <AppearanceProvider>
        <ActionFeedbackProvider>
          <AuthProvider onRestored={markSessionRestored}>
            {fontsReady ? (
              <ModelsProvider>
                <TodosProvider>
                  <NetworkProvider>
                    <PushNotificationBootstrap />
                    <OpenedDocumentBootstrap />
                    <AiConsentRedirect />
                    <RootNavigator />
                    <DialogHost />
                  </NetworkProvider>
                </TodosProvider>
              </ModelsProvider>
            ) : null}
          </AuthProvider>
        </ActionFeedbackProvider>
        <LaunchReveal />
      </AppearanceProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
});

/**
 * A crash no screen or section caught (the chat, the sign-in flow, or this
 * layout itself) shows the shared error view in place of the whole app.
 */
export { ScreenErrorBoundary as ErrorBoundary } from "@/components/ScreenErrorBoundary";
