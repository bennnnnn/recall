import "@/lib/i18n";

import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SpaceMono_400Regular } from "@expo-google-fonts/space-mono";
import { useFonts } from "expo-font";
import * as SplashScreen from "expo-splash-screen";
import { useEffect } from "react";
import { InteractionManager, StyleSheet } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useTranslation } from "react-i18next";

import { AuthProvider } from "@/contexts/AuthContext";
import { AiConsentRedirect } from "@/features/auth/components/AiConsentRedirect";
import { ActionFeedbackProvider } from "@/contexts/ActionFeedbackContext";
import { AppearanceProvider } from "@/contexts/AppearanceContext";
import { ModelsProvider } from "@/contexts/ModelsContext";
import { NetworkProvider, useNetwork } from "@/contexts/NetworkContext";
import { TodosProvider } from "@/features/todos/context/TodosContext";
import { PushNotificationBootstrap } from "@/components/PushNotificationBootstrap";
import { OfflineBanner } from "@/components/OfflineBanner";
import { stackBackOptions } from "@/ui/controls/StackBackButton";
import { DialogHost } from "@/ui/overlay/DialogHost";
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

SplashScreen.preventAutoHideAsync().catch(() => {});

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
  useFonts({
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

  useEffect(() => {
    SplashScreen.hideAsync().catch(() => {});
  }, []);

  useEffect(() => {
    const task = InteractionManager.runAfterInteractions(() => {
      initMobileSentry();
    });
    return () => task.cancel();
  }, []);

  return (
    <GestureHandlerRootView style={styles.root}>
      <AppearanceProvider>
        <ActionFeedbackProvider>
          <AuthProvider>
            <ModelsProvider>
              <TodosProvider>
                <NetworkProvider>
                  <PushNotificationBootstrap />
                  <AiConsentRedirect />
                  <RootNavigator />
                  <DialogHost />
                </NetworkProvider>
              </TodosProvider>
            </ModelsProvider>
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
