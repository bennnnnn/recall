import { Stack } from "expo-router";
import { ActivityIndicator, View } from "react-native";
import { useFonts, SpaceMono_400Regular } from "@expo-google-fonts/space-mono";
import * as SplashScreen from "expo-splash-screen";
import { useEffect } from "react";

import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { C } from "@/constants/Colors";

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

  if (loading) {
    return (
      <View
        style={{
          flex: 1,
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: C.bg,
        }}
      >
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
        options={{ ...HEADER, headerShown: true, title: "Memory" }}
      />
      <Stack.Screen
        name="settings"
        options={{ ...HEADER, headerShown: true, title: "Settings" }}
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

export { ErrorBoundary } from "expo-router";
