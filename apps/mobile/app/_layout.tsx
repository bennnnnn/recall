import "@/lib/i18n";

import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SpaceMono_400Regular } from "@expo-google-fonts/space-mono";
import { useFonts } from "expo-font";
import { useEffect, useState } from "react";
import { InteractionManager, StyleSheet } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useTranslation } from "react-i18next";

import { AuthProvider } from "@/contexts/AuthContext";
import { AiConsentRedirect } from "@/features/auth/components/AiConsentRedirect";
import { ActionFeedbackProvider } from "@/contexts/ActionFeedbackContext";
import { AppearanceProvider } from "@/contexts/AppearanceContext";
import { HomeProvider } from "@/features/home/context/HomeContext";
import { ModelsProvider } from "@/contexts/ModelsContext";
import { NetworkProvider, useNetwork } from "@/contexts/NetworkContext";
import { TodosProvider } from "@/features/todos/context/TodosContext";
import { PushNotificationBootstrap } from "@/components/PushNotificationBootstrap";
import { OfflineBanner } from "@/components/OfflineBanner";
import { stackBackOptions } from "@/ui/controls/StackBackButton";
import { DialogHost } from "@/ui/overlay/DialogHost";
import { restoreLaunchPrefs } from "@/lib/launchPrefs";
import { markLaunchReady, SPLASH_MAX_MS } from "@/lib/launchSplash";
import { useReduceMotion } from "@/lib/reduceMotion";
import { useStackHeaderOptions } from "@/lib/stackHeader";
import {
  stackAuthTransition,
  stackHomeTransition,
  stackPushTransition,
  stackUtilityTransition,
} from "@/lib/stackTransitions";
import { initMobileSentry } from "@/lib/sentry";
import { useTheme } from "@/lib/theme";
import { UI_FONT } from "@/lib/uiFont";

// Before the first render: the user's appearance, accent and language.
void restoreLaunchPrefs().then(() => markLaunchReady("prefs"));

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

/**
 * The faces the app draws with. True once they are in, or failed, or slower
 * than the splash may wait (a dev server): text laid out before its font is
 * registered keeps the system face, so the app draws only after this.
 */
function useLaunchFonts(): boolean {
  const [loaded, error] = useFonts({
    SpaceMono: SpaceMono_400Regular,
    KaTeX_Main: require("katex/dist/fonts/KaTeX_Main-Regular.ttf"),
    KaTeX_MathItalic: require("katex/dist/fonts/KaTeX_Math-Italic.ttf"),
    KaTeX_AMS: require("katex/dist/fonts/KaTeX_AMS-Regular.ttf"),
    // ∬ ∭ ∮ on the math keyboard live only in this face.
    KaTeX_Size1: require("katex/dist/fonts/KaTeX_Size1-Regular.ttf"),
    [UI_FONT.regular]: require("@expo-google-fonts/source-sans-3/400Regular/SourceSans3_400Regular.ttf"),
    [UI_FONT.medium]: require("@expo-google-fonts/source-sans-3/500Medium/SourceSans3_500Medium.ttf"),
    [UI_FONT.semibold]: require("@expo-google-fonts/source-sans-3/600SemiBold/SourceSans3_600SemiBold.ttf"),
    [UI_FONT.bold]: require("@expo-google-fonts/source-sans-3/700Bold/SourceSans3_700Bold.ttf"),
    [UI_FONT.italic]: require("@expo-google-fonts/source-sans-3/400Regular_Italic/SourceSans3_400Regular_Italic.ttf"),
    [UI_FONT.semiboldItalic]: require("@expo-google-fonts/source-sans-3/600SemiBold_Italic/SourceSans3_600SemiBold_Italic.ttf"),
    [UI_FONT.boldItalic]: require("@expo-google-fonts/source-sans-3/700Bold_Italic/SourceSans3_700Bold_Italic.ttf"),
  });
  const [waitedEnough, setWaitedEnough] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setWaitedEnough(true), SPLASH_MAX_MS);
    return () => clearTimeout(timer);
  }, []);
  const ready = loaded || error !== null || waitedEnough;
  useEffect(() => {
    if (ready) markLaunchReady("fonts");
  }, [ready]);
  return ready;
}

export default function RootLayout() {
  const fontsReady = useLaunchFonts();

  useEffect(() => {
    const task = InteractionManager.runAfterInteractions(() => {
      void initMobileSentry();
    });
    return () => task.cancel();
  }, []);

  return (
    <GestureHandlerRootView style={styles.root}>
      <AppearanceProvider>
        <ActionFeedbackProvider>
          <AuthProvider onRestored={markSessionRestored}>
            {fontsReady ? (
              <ModelsProvider>
                <TodosProvider>
                  <HomeProvider>
                    <NetworkProvider>
                      <PushNotificationBootstrap />
                      <AiConsentRedirect />
                      <RootNavigator />
                      <DialogHost />
                    </NetworkProvider>
                  </HomeProvider>
                </TodosProvider>
              </ModelsProvider>
            ) : null}
          </AuthProvider>
        </ActionFeedbackProvider>
      </AppearanceProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
});

// ErrorBoundary is re-exported for expo-router to use automatically when
// errors occur in child routes (it catches crashes in screens).
export { ErrorBoundary } from "expo-router";
