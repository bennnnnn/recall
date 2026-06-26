import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Redirect } from "expo-router";

import { C } from "@/constants/Colors";
import { useAuth } from "@/contexts/AuthContext";
import { checkHealth } from "@/lib/api";
import { config, getApiUrl } from "@/lib/config";
import { isExpoGo } from "@/lib/google-auth";

function GoogleG() {
  return (
    <View style={g.circle}>
      <Text style={g.text}>G</Text>
    </View>
  );
}

export default function LoginScreen() {
  const { token, loading, onboarded, signInWithGoogle, signInWithDev } =
    useAuth();
  const [busy, setBusy] = useState<"google" | "dev" | null>(null);

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color={C.primary} />
      </View>
    );
  }

  if (token) return <Redirect href="/(drawer)" />;
  if (!onboarded) return <Redirect href="/onboarding" />;

  const handleGoogle = async () => {
    setBusy("google");
    try {
      await signInWithGoogle();
    } catch (e) {
      Alert.alert(
        "Sign-in failed",
        e instanceof Error ? e.message : "Try again",
      );
    } finally {
      setBusy(null);
    }
  };

  const handleDev = async () => {
    setBusy("dev");
    try {
      const ok = await checkHealth();
      if (!ok) throw new Error(`API unreachable at ${getApiUrl()}`);
      await signInWithDev();
    } catch (e) {
      Alert.alert("Dev login", e instanceof Error ? e.message : "Login failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <View style={s.root}>
      <View style={s.hero}>
        <View style={s.iconWrap}>
          <View style={s.iconBubble}>
            <Text style={s.iconStar}>✦</Text>
          </View>
          <Text style={s.sp1}>✦</Text>
          <Text style={s.sp2}>·</Text>
          <Text style={s.sp3}>✦</Text>
        </View>
        <Text style={s.title}>Recall</Text>
        <Text style={s.subtitle}>Your AI that remembers you.</Text>
      </View>

      <View style={s.sheet}>
        <Pressable
          style={[s.googleBtn, (busy === "google" || isExpoGo()) && s.dim]}
          onPress={handleGoogle}
          disabled={!!busy || isExpoGo()}
        >
          {busy === "google" ? (
            <ActivityIndicator color="#333" />
          ) : (
            <>
              <GoogleG />
              <Text style={s.googleText}>
                {isExpoGo()
                  ? "Google Sign-In (dev build only)"
                  : "Continue with Google"}
              </Text>
            </>
          )}
        </Pressable>

        <Text style={s.caption}>We only use Google to sign you in.</Text>

        {config.devAuthEnabled && (
          <Pressable
            style={[s.devBtn, busy === "dev" && s.dim]}
            onPress={handleDev}
            disabled={!!busy}
          >
            {busy === "dev" ? (
              <ActivityIndicator color={C.primary} />
            ) : (
              <Text style={s.devText}>Continue as Dev User</Text>
            )}
          </Pressable>
        )}

        <View style={s.links}>
          <Text style={s.link}>Terms</Text>
          <Text style={s.dot}> · </Text>
          <Text style={s.link}>Privacy</Text>
        </View>
      </View>
    </View>
  );
}

const g = StyleSheet.create({
  circle: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: "#4285F4",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 8,
  },
  text: { color: "#fff", fontSize: 13, fontWeight: "700" },
});

const s = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: C.bg,
  },
  root: { flex: 1, backgroundColor: "#F0EBFF" },
  hero: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingBottom: 24,
  },
  iconWrap: { position: "relative", marginBottom: 20 },
  iconBubble: {
    width: 80,
    height: 80,
    borderRadius: 28,
    backgroundColor: C.primary,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: C.primary,
    shadowOpacity: 0.4,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 },
    elevation: 10,
  },
  iconStar: { fontSize: 32, color: "#fff" },
  sp1: {
    position: "absolute",
    top: -12,
    right: -16,
    fontSize: 16,
    color: C.primary,
    opacity: 0.7,
  },
  sp2: {
    position: "absolute",
    bottom: 0,
    left: -18,
    fontSize: 22,
    color: C.primary,
    opacity: 0.4,
  },
  sp3: {
    position: "absolute",
    bottom: -10,
    right: -6,
    fontSize: 12,
    color: C.primaryDark,
    opacity: 0.6,
  },
  title: {
    fontSize: 40,
    fontWeight: "800",
    color: "#1A0F4F",
    letterSpacing: -1,
  },
  subtitle: { fontSize: 17, color: "#5A4F7A", marginTop: 6 },
  sheet: {
    backgroundColor: C.bg,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    paddingHorizontal: 24,
    paddingTop: 32,
    paddingBottom: 48,
    alignItems: "center",
    gap: 12,
  },
  googleBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    width: "100%",
    borderRadius: 14,
    borderWidth: 1.5,
    borderColor: C.border,
    paddingVertical: 14,
    backgroundColor: C.bg,
  },
  googleText: { fontSize: 16, fontWeight: "600", color: C.text },
  caption: { fontSize: 13, color: C.textTertiary },
  devBtn: {
    width: "100%",
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: "center",
    backgroundColor: C.primaryLight,
  },
  devText: { fontSize: 15, fontWeight: "600", color: C.primary },
  dim: { opacity: 0.5 },
  links: { flexDirection: "row", marginTop: 8 },
  link: { fontSize: 13, color: C.textTertiary },
  dot: { fontSize: 13, color: C.textTertiary },
});
