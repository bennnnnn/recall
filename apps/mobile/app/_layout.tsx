import "@/lib/i18n";

import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useFonts, SpaceMono_400Regular } from "@expo-google-fonts/space-mono";
import * as SplashScreen from "expo-splash-screen";
import { useEffect, useMemo } from "react";
import { StyleSheet } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { useTranslation } from "react-i18next";

import { AuthProvider } from "@/contexts/AuthContext";
import { AppearanceProvider } from "@/contexts/AppearanceContext";
import { HomeProvider } from "@/contexts/HomeContext";
import { ModelsProvider } from "@/contexts/ModelsContext";
import { NetworkProvider, useNetwork } from "@/contexts/NetworkContext";
import { ProjectsProvider } from "@/contexts/ProjectsContext";
import { TodosProvider } from "@/contexts/TodosContext";
import { PushNotificationBootstrap } from "@/components/PushNotificationBootstrap";
import { OfflineBanner } from "@/components/OfflineBanner";
import { StackBackButton } from "@/components/StackBackButton";
import { stackHeaderOptions } from "@/lib/stackHeader";
import {
  stackAuthTransition,
  stackHomeTransition,
  stackPushTransition,
  stackUtilityTransition,
} from "@/lib/stackTransitions";
import { initMobileSentry } from "@/lib/sentry";
import { useTheme } from "@/lib/theme";

initMobileSentry();

SplashScreen.preventAutoHideAsync().catch(() => {});

function RootNavigator() {
  const { t } = useTranslation();
  const theme = useTheme();
  const header = useMemo(() => stackHeaderOptions(theme), [theme]);
  const { isOffline } = useNetwork();

  return (
    <>
      <StatusBar style={theme.isDark ? "light" : "dark"} />
      <OfflineBanner visible={isOffline} />
      <Stack
        screenOptions={{
          ...stackPushTransition(),
          headerShown: false,
          contentStyle: { backgroundColor: theme.bg },
        }}
      >
        <Stack.Screen name="login" options={stackAuthTransition()} />
        <Stack.Screen name="onboarding" options={stackAuthTransition()} />
        <Stack.Screen
          name="index"
          options={{ ...stackHomeTransition(), title: "", headerShown: false }}
        />
        <Stack.Screen
          name="memory"
          options={{
            ...stackUtilityTransition(),
            ...header,
            headerShown: true,
            title: t("memory.title"),
            headerBackVisible: false,
            headerLeft: () => <StackBackButton />,
          }}
        />
        <Stack.Screen
          name="settings"
          options={{ ...stackPushTransition(), headerShown: false }}
        />
        <Stack.Screen
          name="todos"
          options={{
            ...stackUtilityTransition(),
            ...header,
            headerShown: true,
            title: t("todos.title"),
            headerBackVisible: false,
            headerLeft: () => <StackBackButton />,
          }}
        />
        <Stack.Screen
          name="projects"
          options={{ ...stackPushTransition(), headerShown: false }}
        />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts({
    SpaceMono: SpaceMono_400Regular,
  });

  useEffect(() => {
    if (fontsLoaded || fontError) {
      SplashScreen.hideAsync().catch(() => {});
    }
  }, [fontsLoaded, fontError]);

  if (!fontsLoaded && !fontError) {
    return null;
  }

  return (
    <GestureHandlerRootView style={styles.root}>
      <AppearanceProvider>
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
