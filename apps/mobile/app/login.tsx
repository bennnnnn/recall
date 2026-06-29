import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Redirect, router } from "expo-router";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/contexts/AuthContext";
import { isExpoGo } from "@/lib/google-auth";
import { Theme, useTheme } from "@/lib/theme";

function GoogleG() {
  return (
    <View style={g.circle}>
      <Text style={g.text}>G</Text>
    </View>
  );
}

export default function LoginScreen() {
  const { token, loading, onboarded, signInWithGoogle } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [busy, setBusy] = useState(false);

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color={theme.primary} />
      </View>
    );
  }

  if (token) return <Redirect href="/" />;
  if (!onboarded) return <Redirect href="/onboarding" />;

  const handleGoogle = async () => {
    if (isExpoGo()) {
      Alert.alert(
        t("login.google_unavailable_title"),
        t("login.google_unavailable_body"),
      );
      return;
    }
    setBusy(true);
    try {
      await signInWithGoogle();
    } catch (e) {
      Alert.alert(
        "Sign-in failed",
        e instanceof Error ? e.message : "Try again",
      );
    } finally {
      setBusy(false);
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
        <Text style={s.subtitle}>{t("login.tagline")}</Text>
      </View>

      <View style={s.sheet}>
        <Pressable
          style={[s.googleBtn, busy && s.dim]}
          onPress={handleGoogle}
          disabled={busy}
        >
          {busy ? (
            <ActivityIndicator color={theme.textSecondary} />
          ) : (
            <>
              <GoogleG />
              <Text style={s.googleText}>{t("login.google")}</Text>
            </>
          )}
        </Pressable>

        <View style={s.links}>
          <Text style={s.link}>{t("login.terms")}</Text>
          <Text style={s.dot}> · </Text>
          <Pressable onPress={() => router.push("/privacy")}>
            <Text style={s.link}>{t("login.privacy")}</Text>
          </Pressable>
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

function makeStyles(theme: Theme) {
  const heroTint = theme.isDark ? theme.primaryLight : "#F0EBFF";
  const titleColor = theme.isDark ? theme.text : "#1A0F4F";
  const subtitleColor = theme.isDark ? theme.textSecondary : "#5A4F7A";

  return StyleSheet.create({
    center: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: theme.bg,
    },
    root: { flex: 1, backgroundColor: heroTint },
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
      backgroundColor: theme.primary,
      alignItems: "center",
      justifyContent: "center",
      boxShadow: theme.isDark
        ? undefined
        : "0 8 16 0 rgba(108, 71, 255, 0.4)",
      elevation: 10,
    },
    iconStar: { fontSize: 32, color: "#fff" },
    sp1: {
      position: "absolute",
      top: -12,
      right: -16,
      fontSize: 16,
      color: theme.primary,
      opacity: 0.7,
    },
    sp2: {
      position: "absolute",
      bottom: 0,
      left: -18,
      fontSize: 22,
      color: theme.primary,
      opacity: 0.4,
    },
    sp3: {
      position: "absolute",
      bottom: -10,
      right: -6,
      fontSize: 12,
      color: theme.primaryDark,
      opacity: 0.6,
    },
    title: {
      fontSize: 40,
      fontWeight: "800",
      color: titleColor,
      letterSpacing: -1,
    },
    subtitle: { fontSize: 17, color: subtitleColor, marginTop: 6 },
    sheet: {
      backgroundColor: theme.bg,
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
      borderColor: theme.border,
      paddingVertical: 14,
      backgroundColor: theme.bg,
    },
    googleText: { fontSize: 16, fontWeight: "600", color: theme.text },
    dim: { opacity: 0.5 },
    links: { flexDirection: "row", marginTop: 8 },
    link: { fontSize: 13, color: theme.textTertiary },
    dot: { fontSize: 13, color: theme.textTertiary },
  });
}
