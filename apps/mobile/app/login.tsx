import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  Linking,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { Redirect } from "expo-router";
import { useTranslation } from "react-i18next";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
import { useAuth } from "@/contexts/AuthContext";
import {
  formatAppleSignInError,
  shouldShowAppleSignInButton,
} from "@/lib/apple-auth";
import { config, isGoogleSignInConfigured, isGoogleWebClientConfigured } from "@/lib/config";
import { formatGoogleSignInError, isExpoGo } from "@/lib/google-auth";
import { tap } from "@/lib/haptics";
import { getLegalPrivacyUrl, getLegalTermsUrl } from "@/lib/legalUrls";
import { Theme, useTheme, withAlpha } from "@/lib/theme";

/** Frosted-glass tint over the hero gradient — deliberately theme-invariant
 * white, unlike the primary-tinted border below (which DOES follow theme). */
const GLASS_WHITE = "#FFFFFF";

const APP_ICON = require("@/assets/images/icon.png");

const HIGHLIGHTS = [
  { icon: "school-outline" as const, labelKey: "login.highlight_learn" },
  { icon: "calendar-outline" as const, labelKey: "login.highlight_organize" },
  { icon: "sparkles-outline" as const, labelKey: "login.highlight_remember" },
];

export default function LoginScreen() {
  const { token, loading, onboarded, signInWithApple, signInWithGoogle, signInWithDev } =
    useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [busyProvider, setBusyProvider] = useState<"apple" | "google" | "dev" | null>(null);
  const busy = busyProvider !== null;
  const showDevLogin = config.devAuthEnabled && __DEV__;
  const showGoogleLogin =
    !isExpoGo() &&
    (Platform.OS === "android" ? isGoogleWebClientConfigured() : isGoogleSignInConfigured());
  const showAppleLogin = shouldShowAppleSignInButton();
  const googleOnlyDevBuild = !isExpoGo() && showDevLogin && showGoogleLogin;
  const expoGoIos = isExpoGo() && Platform.OS === "ios";
  const expoGoAndroid = isExpoGo() && Platform.OS === "android";

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color={theme.primary} />
      </View>
    );
  }

  if (token) return <Redirect href="/" />;
  if (!onboarded) return <Redirect href="/onboarding" />;

  const signInErrorMessage = (error: unknown, provider: "google" | "apple") => {
    const key =
      provider === "google" ? formatGoogleSignInError(error) : formatAppleSignInError(error);
    if (key === "bundle_load_failed") return t("login.error_bundle");
    if (key === "native_module_missing") return t("login.error_native_module");
    if (key === "not_configured") return t("login.error_not_configured");
    if (key === "android_oauth_setup") return t("login.error_android_google");
    if (key === "generic") return t("login.error_generic");
    return key;
  };

  const handleApple = async () => {
    tap();
    setBusyProvider("apple");
    try {
      await signInWithApple();
    } catch (e) {
      Alert.alert(t("login.sign_in_failed"), signInErrorMessage(e, "apple"));
    } finally {
      setBusyProvider(null);
    }
  };

  const handleGoogle = async () => {
    tap();
    if (isExpoGo()) {
      Alert.alert(
        t("login.google_unavailable_title"),
        t("login.google_unavailable_body"),
      );
      return;
    }
    if (!isGoogleWebClientConfigured()) {
      Alert.alert(t("login.sign_in_failed"), t("login.error_not_configured"));
      return;
    }
    if (Platform.OS === "ios" && !isGoogleSignInConfigured()) {
      Alert.alert(t("login.sign_in_failed"), t("login.error_not_configured"));
      return;
    }
    setBusyProvider("google");
    try {
      await signInWithGoogle();
    } catch (e) {
      Alert.alert(t("login.sign_in_failed"), signInErrorMessage(e, "google"));
    } finally {
      setBusyProvider(null);
    }
  };

  const handleDev = async () => {
    tap();
    setBusyProvider("dev");
    try {
      await signInWithDev();
    } catch (e) {
      Alert.alert(
        t("login.sign_in_failed"),
        e instanceof Error ? e.message : t("login.error_generic"),
      );
    } finally {
      setBusyProvider(null);
    }
  };

  const gradientColors = [theme.primaryLight, theme.bg] as const;

  return (
    <LinearGradient colors={gradientColors} style={s.root}>
      <SafeAreaView style={s.safe} edges={["top", "bottom"]}>
        <View style={s.hero}>
          <View style={s.logoGlow}>
            <Image source={APP_ICON} style={s.logo} accessibilityLabel="Recall" />
          </View>
          <Text style={s.title}>Recall</Text>
          <Text style={s.subtitle}>{t("login.tagline")}</Text>

          <View style={s.highlights}>
            {HIGHLIGHTS.map((item) => (
              <View key={item.labelKey} style={s.highlight}>
                <View style={s.highlightIcon}>
                  <Ionicons name={item.icon} size={16} color={theme.primary} />
                </View>
                <Text style={s.highlightText}>{t(item.labelKey)}</Text>
              </View>
            ))}
          </View>
        </View>

        <View style={s.actions}>
          {expoGoAndroid && showDevLogin ? (
            <>
              <View style={s.devBanner}>
                <Ionicons name="information-circle-outline" size={18} color={theme.primary} />
                <Text style={s.devBannerText}>{t("login.dev_expo_hint")}</Text>
              </View>
              <Button
                title={t("login.dev")}
                onPress={handleDev}
                loading={busyProvider === "dev"}
                disabled={busy}
                style={s.primaryBtn}
              />
            </>
          ) : (
            <>
              {expoGoIos ? (
                <View style={s.devBanner}>
                  <Ionicons name="information-circle-outline" size={18} color={theme.primary} />
                  <Text style={s.devBannerText}>{t("login.dev_expo_ios_hint")}</Text>
                </View>
              ) : null}
              {showAppleLogin ? (
                <Pressable
                  style={[s.appleBtn, busy && s.dim]}
                  onPress={handleApple}
                  disabled={busy}
                  accessibilityRole="button"
                  accessibilityLabel={t("login.apple")}
                  accessibilityState={{ disabled: busy, busy: busyProvider === "apple" }}
                >
                  {busyProvider === "apple" ? (
                    <ActivityIndicator color="#FFFFFF" />
                  ) : (
                    <>
                      <Ionicons name="logo-apple" size={20} color="#FFFFFF" />
                      <Text style={s.appleText}>{t("login.apple")}</Text>
                    </>
                  )}
                </Pressable>
              ) : null}
              {showGoogleLogin ? (
                <Pressable
                  style={[s.googleBtn, busy && s.dim]}
                  onPress={handleGoogle}
                  disabled={busy}
                  accessibilityRole="button"
                  accessibilityLabel={t("login.google")}
                  accessibilityState={{ disabled: busy, busy: busyProvider === "google" }}
                >
                  {busyProvider === "google" ? (
                    <ActivityIndicator color={theme.textSecondary} />
                  ) : (
                    <>
                      <Ionicons name="logo-google" size={20} color="#4285F4" />
                      <Text style={s.googleText}>{t("login.google")}</Text>
                    </>
                  )}
                </Pressable>
              ) : showDevLogin && !showAppleLogin ? (
                <View style={s.devBanner}>
                  <Ionicons name="information-circle-outline" size={18} color={theme.primary} />
                  <Text style={s.devBannerText}>{t("login.error_not_configured")}</Text>
                </View>
              ) : null}
              {googleOnlyDevBuild ? (
                <>
                  <Text style={s.orText}>{t("login.or_dev")}</Text>
                  <Pressable
                    style={[s.devSecondaryBtn, busy && s.dim]}
                    onPress={handleDev}
                    disabled={busy}
                    accessibilityRole="button"
                    accessibilityLabel={t("login.dev")}
                    accessibilityState={{ disabled: busy, busy: busyProvider === "dev" }}
                  >
                    <Text style={s.devSecondaryText}>{t("login.dev")}</Text>
                  </Pressable>
                </>
              ) : showDevLogin && !showGoogleLogin && !showAppleLogin ? (
                <Button
                  title={t("login.dev")}
                  onPress={handleDev}
                  loading={busyProvider === "dev"}
                  disabled={busy}
                  style={s.primaryBtn}
                />
              ) : showDevLogin && expoGoIos ? (
                <>
                  <Text style={s.orText}>{t("login.or_dev")}</Text>
                  <Pressable
                    style={[s.devSecondaryBtn, busy && s.dim]}
                    onPress={handleDev}
                    disabled={busy}
                    accessibilityRole="button"
                    accessibilityLabel={t("login.dev")}
                    accessibilityState={{ disabled: busy, busy: busyProvider === "dev" }}
                  >
                    <Text style={s.devSecondaryText}>{t("login.dev")}</Text>
                  </Pressable>
                </>
              ) : null}
            </>
          )}

          <View style={s.links}>
            <Pressable
              onPress={() => void Linking.openURL(getLegalTermsUrl())}
              accessibilityRole="link"
              accessibilityLabel={t("login.terms")}
            >
              <Text style={[s.link, s.linkPressable]}>{t("login.terms")}</Text>
            </Pressable>
            <Text style={s.dot}>·</Text>
            <Pressable
              onPress={() => void Linking.openURL(getLegalPrivacyUrl())}
              accessibilityRole="link"
              accessibilityLabel={t("login.privacy")}
            >
              <Text style={[s.link, s.linkPressable]}>{t("login.privacy")}</Text>
            </Pressable>
          </View>
        </View>
      </SafeAreaView>
    </LinearGradient>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    center: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: theme.bg,
    },
    root: { flex: 1 },
    safe: {
      flex: 1,
      paddingHorizontal: 24,
      justifyContent: "space-between",
    },
    hero: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingTop: 12,
      paddingBottom: 24,
    },
    logoGlow: {
      borderRadius: 28,
      marginBottom: 20,
      ...Platform.select({
        ios: {
          shadowColor: theme.primary,
          shadowOffset: { width: 0, height: 10 },
          shadowOpacity: theme.isDark ? 0.35 : 0.28,
          shadowRadius: 18,
        },
        android: { elevation: 8 },
      }),
    },
    logo: {
      width: 88,
      height: 88,
      borderRadius: 24,
    },
    title: {
      fontSize: 36,
      fontWeight: "800",
      color: theme.text,
      letterSpacing: -1,
    },
    subtitle: {
      fontSize: 16,
      lineHeight: 24,
      color: theme.textSecondary,
      marginTop: 8,
      textAlign: "center",
      maxWidth: 300,
      paddingHorizontal: 8,
    },
    highlights: {
      flexDirection: "row",
      flexWrap: "wrap",
      justifyContent: "center",
      gap: 10,
      marginTop: 28,
      maxWidth: 340,
    },
    highlight: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      backgroundColor: theme.isDark ? theme.surface : withAlpha(GLASS_WHITE, 0.72),
      borderRadius: 999,
      paddingHorizontal: 12,
      paddingVertical: 8,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.isDark ? theme.border : withAlpha(theme.primary, 0.12),
    },
    highlightIcon: {
      width: 24,
      height: 24,
      borderRadius: 12,
      backgroundColor: theme.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    highlightText: {
      fontSize: 13,
      fontWeight: "600",
      color: theme.textSecondary,
    },
    actions: {
      paddingBottom: 8,
      gap: 14,
    },
    devBanner: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: 10,
      backgroundColor: withAlpha(GLASS_WHITE, theme.isDark ? 0.08 : 0.5),
      borderRadius: 14,
      paddingHorizontal: 14,
      paddingVertical: 12,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.isDark
        ? withAlpha(GLASS_WHITE, 0.1)
        : withAlpha(theme.primary, 0.12),
    },
    devBannerText: {
      flex: 1,
      fontSize: 13,
      lineHeight: 19,
      color: theme.textSecondary,
    },
    primaryBtn: {
      alignSelf: "stretch",
      width: "100%",
    },
    appleBtn: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 10,
      width: "100%",
      borderRadius: 16,
      paddingVertical: 16,
      backgroundColor: "#000000",
    },
    appleText: { fontSize: 16, fontWeight: "600", color: "#FFFFFF" },
    googleBtn: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 10,
      width: "100%",
      borderRadius: 16,
      borderWidth: 1.5,
      borderColor: theme.isDark
        ? withAlpha(GLASS_WHITE, 0.12)
        : withAlpha(theme.primary, 0.18),
      paddingVertical: 16,
      backgroundColor: withAlpha(GLASS_WHITE, theme.isDark ? 0.08 : 0.55),
    },
    googleText: { fontSize: 16, fontWeight: "600", color: theme.text },
    orText: {
      fontSize: 13,
      fontWeight: "600",
      color: theme.textTertiary,
      textAlign: "center",
    },
    devSecondaryBtn: {
      alignItems: "center",
      justifyContent: "center",
      width: "100%",
      borderRadius: 16,
      borderWidth: 1.5,
      borderColor: theme.isDark
        ? withAlpha(GLASS_WHITE, 0.12)
        : withAlpha(theme.primary, 0.18),
      paddingVertical: 14,
      backgroundColor: withAlpha(GLASS_WHITE, theme.isDark ? 0.06 : 0.45),
    },
    devSecondaryText: { fontSize: 15, fontWeight: "600", color: theme.primary },
    dim: { opacity: 0.55 },
    links: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      marginTop: 2,
    },
    link: { fontSize: 13, color: theme.textTertiary },
    linkPressable: { textDecorationLine: "underline" },
    dot: { fontSize: 13, color: theme.textTertiary },
  });
}
