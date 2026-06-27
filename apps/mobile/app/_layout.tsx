import "@/lib/i18n";

import { Stack } from "expo-router";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { useFonts, SpaceMono_400Regular } from "@expo-google-fonts/space-mono";
import * as SplashScreen from "expo-splash-screen";
import { useEffect } from "react";

import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { C } from "@/constants/Colors";
import { useTranslation } from "react-i18next";

SplashScreen.preventAutoHideAsync().catch(() => {});

const HEADER = {
  headerStyle: { backgroundColor: C.bg },
  headerTitleStyle: { fontWeight: "700" as const, fontSize: 17, color: C.text },
  headerShadowVisible: false,
  headerTintColor: C.primary,
  headerBackTitle: "",
};

function RootNavigator() {
  const { loading } = useAuth();
  const { t } = useTranslation();

  if (loading) {
    return (
      <View style={s.loading}>
        <ActivityIndicator size="large" color={C.primary} />
      </View>
    );
  }

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: C.bg },
      }}
    >
      <Stack.Screen name="login" />
      <Stack.Screen name="onboarding" />
      <Stack.Screen name="(drawer)" />
      <Stack.Screen
        name="memory"
        options={{ ...HEADER, headerShown: true, title: t("memory.title") }}
      />
      <Stack.Screen
        name="settings"
        options={{ ...HEADER, headerShown: true, title: t("settings.title") }}
      />
      <Stack.Screen
        name="privacy"
        options={{ ...HEADER, headerShown: true, title: t("privacy.title") }}
      />
      <Stack.Screen
        name="todos"
        options={{ ...HEADER, headerShown: true, title: t("todos.title") }}
      />
      <Stack.Screen
        name="search"
        options={{ headerShown: false }}
      />
    </Stack>
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
    <AuthProvider>
      <RootNavigator />
    </AuthProvider>
  );
}

// ErrorBoundary is re-exported for expo-router to use automatically when
// errors occur in child routes (it catches crashes in screens).
export { ErrorBoundary } from "expo-router";

const s = StyleSheet.create({
  loading: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: C.bg,
  },
});
