import { type ReactNode, useMemo } from "react";
import {
  ActivityIndicator,
  Image,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
  type ViewStyle,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Redirect } from "expo-router";
import { useTranslation } from "react-i18next";

import { AuthScrollLayout } from "@/components/AuthScrollLayout";
import { Button } from "@/ui/controls/Button";
import { BrandMark } from "@/ui/icons/brand";
import { Icon } from "@/ui/icons/Icon";
import { useAuth } from "@/contexts/AuthContext";
import { type LoginProvider, useLoginActions } from "@/features/auth/hooks/useLoginActions";
import { AI_CONSENT_ROUTE, needsAiDataConsent } from "@/features/auth/model/aiConsent";
import { AgreeLine } from "@/features/auth/components/AgreeLine";
import { shouldShowAppleSignInButton } from "@/lib/apple-auth";
import { config, isGoogleSignInConfigured, isGoogleWebClientConfigured } from "@/lib/config";
import { isExpoGo } from "@/lib/google-auth";
import { Space } from "@/lib/space";
import { shadowGlow } from "@/lib/shadow";
import { BrandAccent } from "@/lib/accentRuntime";
import { Theme, useTheme, withAlpha } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { IconSize } from "@/ui/icons/sizes";
import { Radius } from "@/lib/radius";

/** Frosted-glass tint over the hero gradient — deliberately theme-invariant
 * white, unlike the primary-tinted border below (which DOES follow theme). */
// eslint-disable-next-line no-restricted-syntax -- frosted glass is white in both schemes; no theme role means that
const GLASS_WHITE = "#FFFFFF";

const APP_ICON = require("@/assets/images/icon.png");

const HIGHLIGHTS = [
  { icon: "graduation-cap" as const, labelKey: "login.highlight_learn" },
  { icon: "message-dots" as const, labelKey: "login.highlight_organize" },
];

/** Sign-in, in the brand's indigo whatever accent the phone has picked. */
export default function LoginScreen() {
  return (
    <BrandAccent>
      <SignIn />
    </BrandAccent>
  );
}

function SignIn() {
  const { token, user, loading, onboarded } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color={theme.primary} />
      </View>
    );
  }

  // A tap here agrees, so a sign-in comes back agreed and opens the chat. An account the
  // server answers without it (an older API) still sees the consent screen first.
  if (token) return <Redirect href={needsAiDataConsent(user) ? AI_CONSENT_ROUTE : "/"} />;
  if (!onboarded) return <Redirect href="/onboarding" />;

  const gradientColors = [theme.primaryLight, theme.bg] as const;

  return (
    <LinearGradient colors={gradientColors} style={s.root}>
      <AuthScrollLayout justify="space-between" footer={<SignInActions s={s} theme={theme} />}>
        <View style={s.hero}>
          <View style={s.logoGlow}>
            <Image source={APP_ICON} style={s.logo} accessibilityLabel={t("app.name")} />
          </View>
          <Text style={s.title} accessibilityRole="header">{t("app.name")}</Text>
          <Text style={s.subtitle}>{t("login.tagline")}</Text>

          <View style={s.highlights}>
            {HIGHLIGHTS.map((item) => (
              <View key={item.labelKey} style={s.highlight}>
                <View style={s.highlightIcon}>
                  <Icon name={item.icon} size={IconSize.xs} color={theme.primary} />
                </View>
                <Text style={s.highlightText}>{t(item.labelKey)}</Text>
              </View>
            ))}
          </View>
        </View>

      </AuthScrollLayout>
    </LinearGradient>
  );
}

type Styles = ReturnType<typeof makeStyles>;

type ProviderButtonProps = {
  provider: LoginProvider;
  busyProvider: LoginProvider | null;
  label: string;
  onPress: () => void;
  base: ViewStyle;
  spinnerColor: string;
  s: Styles;
  children: ReactNode;
};

/** One way in. Another provider's sign-in dims it; a press shows only while none is busy. */
function ProviderButton({ provider, busyProvider, label, onPress, base, spinnerColor, s, children }: ProviderButtonProps) {
  const busy = busyProvider !== null;
  return (
    <Pressable
      style={({ pressed }) => [
        base,
        busyProvider !== null && busyProvider !== provider && s.dim,
        pressed && busyProvider === null && s.pressed,
      ]}
      onPress={onPress}
      disabled={busy}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: busy, busy: busyProvider === provider }}
    >
      {busyProvider === provider ? <ActivityIndicator size="small" color={spinnerColor} /> : children}
    </Pressable>
  );
}

/** The ways in, and the line a tap agrees to: pinned under the hero by `AuthScrollLayout`. */
function SignInActions({ s, theme }: { s: Styles; theme: Theme }) {
  const { t } = useTranslation();
  const { busyProvider, busy, handleApple, handleGoogle, handleDev } = useLoginActions();
  const showDevLogin = config.devAuthEnabled && __DEV__;
  const showGoogleLogin =
    !isExpoGo() &&
    (Platform.OS === "android" ? isGoogleWebClientConfigured() : isGoogleSignInConfigured());
  const showAppleLogin = shouldShowAppleSignInButton();
  const googleOnlyDevBuild = !isExpoGo() && showDevLogin && showGoogleLogin;
  // Expo Go signs in with neither Google nor Apple: dev login is the way in there.
  const expoGo = isExpoGo();
  const devBanner = (message: string) => (
    <View style={s.devBanner}>
      <Icon name="info" size={IconSize.sm} color={theme.primary} />
      <Text style={s.devBannerText}>{message}</Text>
    </View>
  );
  /** Dev login as the only way in (Expo Go on Android, or no sign-in configured). */
  const devPrimaryLogin = (
    <Button
      title={t("login.dev")}
      onPress={handleDev}
      loading={busyProvider === "dev"}
      loadingLabel={t("login.dev")}
      disabled={busy}
      style={s.primaryBtn}
    />
  );
  /** Dev login under a real sign-in button. */
  const devSecondaryLogin = (
    <>
      <Text style={s.orText}>{t("login.or_dev")}</Text>
      <ProviderButton
        provider="dev"
        busyProvider={busyProvider}
        label={t("login.dev")}
        onPress={handleDev}
        base={s.devSecondaryBtn}
        spinnerColor={theme.primary}
        s={s}
      >
        <Text style={s.devSecondaryText}>{t("login.dev")}</Text>
      </ProviderButton>
    </>
  );

  return (
    <View style={s.actions}>
      {expoGo && showDevLogin ? (
        <>
          {devBanner(t(Platform.OS === "ios" ? "login.dev_expo_ios_hint" : "login.dev_expo_hint"))}
          {devPrimaryLogin}
        </>
      ) : (
        <>
          {showAppleLogin ? (
            <ProviderButton
              provider="apple"
              busyProvider={busyProvider}
              label={t("login.apple")}
              onPress={handleApple}
              base={s.appleBtn}
              spinnerColor={theme.brand.appleInk}
              s={s}
            >
              <BrandMark name="apple" size={IconSize.sm} color={theme.brand.appleInk} />
              <Text style={s.appleText}>{t("login.apple")}</Text>
            </ProviderButton>
          ) : null}
          {showGoogleLogin ? (
            <ProviderButton
              provider="google"
              busyProvider={busyProvider}
              label={t("login.google")}
              onPress={handleGoogle}
              base={s.googleBtn}
              spinnerColor={theme.textSecondary}
              s={s}
            >
              <BrandMark name="google" size={IconSize.sm} />
              <Text style={s.googleText}>{t("login.google")}</Text>
            </ProviderButton>
          ) : showDevLogin && !showAppleLogin ? (
            devBanner(t("login.error_not_configured"))
          ) : null}
          {googleOnlyDevBuild ? (
            devSecondaryLogin
          ) : showDevLogin && !showGoogleLogin && !showAppleLogin ? (
            devPrimaryLogin
          ) : null}
        </>
      )}

      {/* A tap agrees to the Terms and Privacy Policy (features/auth/api.ts sends it with
          the sign-in); the Privacy Policy says what the AI providers receive. */}
      <AgreeLine style={s.consentLine} linkStyle={[s.link, s.linkPressable]} />
    </View>
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
    hero: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingTop: Space.sm,
      paddingBottom: Space.lg,
    },
    logoGlow: {
      borderRadius: Radius.composer,
      marginBottom: Space.gutter,
      ...shadowGlow(theme, theme.primary),
    },
    logo: {
      width: 88,
      height: 88,
      borderRadius: Radius.composer,
    },
    title: {
      ...Type.display,
      color: theme.text,
    },
    subtitle: {
      ...Type.body,
      color: theme.textSecondary,
      marginTop: Space.xs,
      textAlign: "center",
      maxWidth: 300,
      paddingHorizontal: Space.xs,
    },
    highlights: {
      flexDirection: "row",
      flexWrap: "wrap",
      justifyContent: "center",
      gap: Space.xs,
      marginTop: Space.lg,
      maxWidth: 340,
    },
    highlight: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      backgroundColor: theme.isDark ? theme.surface : withAlpha(GLASS_WHITE, 0.72),
      borderRadius: Radius.full,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xs,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.isDark ? theme.border : withAlpha(theme.primary, 0.12),
    },
    highlightIcon: {
      width: 24,
      height: 24,
      borderRadius: Radius.md,
      backgroundColor: theme.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    highlightText: {
      ...Type.caption,
      color: theme.textSecondary,
    },
    actions: {
      paddingBottom: Space.xs,
      gap: Space.sm,
    },
    devBanner: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: Space.xs,
      backgroundColor: withAlpha(GLASS_WHITE, theme.isDark ? 0.08 : 0.5),
      borderRadius: Radius.lg,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.sm,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.isDark
        ? withAlpha(GLASS_WHITE, 0.1)
        : withAlpha(theme.primary, 0.12),
    },
    devBannerText: {
      flex: 1,
      ...Type.caption,
      ...Weight.regular,
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
      gap: Space.xs,
      width: "100%",
      borderRadius: Radius.xl,
      paddingVertical: Space.md,
      backgroundColor: theme.brand.apple,
    },
    appleText: { ...Type.body, ...Weight.semibold, color: theme.brand.appleInk },
    googleBtn: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: Space.xs,
      width: "100%",
      borderRadius: Radius.xl,
      borderWidth: 1.5,
      borderColor: theme.isDark
        ? withAlpha(GLASS_WHITE, 0.12)
        : withAlpha(theme.primary, 0.18),
      paddingVertical: Space.md,
      backgroundColor: withAlpha(GLASS_WHITE, theme.isDark ? 0.08 : 0.55),
    },
    googleText: { ...Type.body, ...Weight.semibold, color: theme.text },
    orText: {
      ...Type.caption,
      color: theme.textTertiary,
      textAlign: "center",
    },
    devSecondaryBtn: {
      alignItems: "center",
      justifyContent: "center",
      width: "100%",
      borderRadius: Radius.xl,
      borderWidth: 1.5,
      borderColor: theme.isDark
        ? withAlpha(GLASS_WHITE, 0.12)
        : withAlpha(theme.primary, 0.18),
      paddingVertical: Space.sm,
      backgroundColor: withAlpha(GLASS_WHITE, theme.isDark ? 0.06 : 0.45),
    },
    devSecondaryText: { ...Type.secondary, ...Weight.semibold, color: theme.primary },
    dim: { opacity: 0.55 },
    pressed: { opacity: 0.85 },
    consentLine: {
      ...Type.caption,
      ...Weight.regular,
      color: theme.textSecondary,
      textAlign: "center",
    },
    link: { ...Type.caption, ...Weight.regular, color: theme.primary },
    linkPressable: { textDecorationLine: "underline" },
  });
}
