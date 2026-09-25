import "@/lib/i18n";

import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SpaceMono_400Regular } from "@expo-google-fonts/space-mono";
import { useFonts } from "expo-font";
import * as SplashScreen from "expo-splash-screen";
import { useEffect, useMemo } from "react";
import { InteractionManager, StyleSheet } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useTranslation } from "react-i18next";

import { AuthProvider } from "@/contexts/AuthContext";
import { ActionFeedbackProvider } from "@/contexts/ActionFeedbackContext";
import { AppearanceProvider } from "@/contexts/AppearanceContext";
import { HomeProvider } from "@/features/home/context/HomeContext";
import { ModelsProvider } from "@/contexts/ModelsContext";
import { NetworkProvider, useNetwork } from "@/contexts/NetworkContext";
import { ProjectsProvider } from "@/features/learning/context/ProjectsContext";
import { TodosProvider } from "@/features/todos/context/TodosContext";
import { PushNotificationBootstrap } from "@/components/PushNotificationBootstrap";
import { OfflineBanner } from "@/components/OfflineBanner";
import { StackBackButton } from "@/ui/controls/StackBackButton";
import { useReduceMotion } from "@/lib/reduceMotion";
import { stackHeaderOptions } from "@/lib/stackHeader";
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
  const header = useMemo(() => stackHeaderOptions(theme), [theme]);
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
        <Stack.Screen
          name="index"
          options={{ ...stackHomeTransition(), title: "", headerShown: false }}
        />
        <Stack.Screen
          name="memory"
          options={{
            ...stackUtilityTransition(reduceMotion),
            ...header,
            headerShown: true,
            title: t("memory.title"),
            headerBackVisible: false,
            headerLeft: () => <StackBackButton />,
          }}
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
            headerLeft: () => <StackBackButton />,
          }}
        />
        <Stack.Screen
          name="projects"
          options={{ ...stackPushTransition(reduceMotion), headerShown: false }}
        />
        {/* Nested-stack drawer hubs share one transition preset. */}
        <Stack.Screen
          name="my-job"
          options={{ ...stackPushTransition(reduceMotion), headerShown: false }}
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
            headerLeft: () => <StackBackButton />,
          }}
        />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  useFonts({
    SpaceMono: SpaceMono_400Regular,
    SourceSerif4: require("@expo-google-fonts/source-serif-4/400Regular/SourceSerif4_400Regular.ttf"),
    [UI_FONT.regular]: require("@expo-google-fonts/source-sans-3/400Regular/SourceSans3_400Regular.ttf"),
    [UI_FONT.medium]: require("@expo-google-fonts/source-sans-3/500Medium/SourceSans3_500Medium.ttf"),
    [UI_FONT.semibold]: require("@expo-google-fonts/source-sans-3/600SemiBold/SourceSans3_600SemiBold.ttf"),
    [UI_FONT.bold]: require("@expo-google-fonts/source-sans-3/700Bold/SourceSans3_700Bold.ttf"),
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
                <ProjectsProvider>
                  <HomeProvider>
                    <NetworkProvider>
                      <PushNotificationBootstrap />
                      <RootNavigator />
                    </NetworkProvider>
                  </HomeProvider>
                </ProjectsProvider>
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
