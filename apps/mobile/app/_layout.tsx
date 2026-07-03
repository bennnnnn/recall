import "@/lib/i18n";

import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useFonts, SpaceMono_400Regular } from "@expo-google-fonts/space-mono";
import * as SplashScreen from "expo-splash-screen";
import { useEffect, useMemo } from "react";

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
import { initMobileSentry } from "@/lib/sentry";
import { useTheme } from "@/lib/theme";
import { useTranslation } from "react-i18next";

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
        headerShown: false,
        contentStyle: { backgroundColor: theme.bg },
        animation: "slide_from_right",
      }}
    >
      <Stack.Screen name="login" />
      <Stack.Screen name="onboarding" />
      <Stack.Screen name="index" options={{ title: "", headerShown: false }} />
      <Stack.Screen
        name="memory"
        options={{
          ...header,
          headerShown: true,
          title: t("memory.title"),
          headerBackVisible: false,
          headerLeft: () => <StackBackButton />,
        }}
      />
      <Stack.Screen name="settings" options={{ headerShown: false }} />
      <Stack.Screen
        name="todos"
        options={{
          ...header,
          headerShown: true,
          title: t("todos.title"),
          headerBackVisible: false,
          headerLeft: () => <StackBackButton />,
        }}
      />
      <Stack.Screen name="projects" options={{ headerShown: false }} />
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
  );
}

// ErrorBoundary is re-exported for expo-router to use automatically when
// errors occur in child routes (it catches crashes in screens).
export { ErrorBoundary } from "expo-router";
