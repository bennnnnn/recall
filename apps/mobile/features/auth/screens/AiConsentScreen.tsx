import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Redirect } from "expo-router";
import { useTranslation } from "react-i18next";

import { AuthScrollLayout } from "@/components/AuthScrollLayout";
import { useAuth } from "@/contexts/AuthContext";
import { useAiConsentActions } from "@/features/auth/hooks/useAiConsentActions";
import { needsAiDataConsent } from "@/features/auth/model/aiConsent";
import { getLegalPrivacyUrl } from "@/lib/legalUrls";
import { openAllowedUrl } from "@/lib/linkSchemePolicy";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { BrandAccent } from "@/lib/accentRuntime";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { Button } from "@/ui/controls/Button";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";

/**
 * One sentence on what Recall sends to outside AI and search services, the privacy policy
 * for the detail, and agree, sign out or delete: nothing to read through (owner,
 * 2026-11-25). A
 * sign-in agrees by its tap (the line on LoginScreen), so this asks only an account
 * without the agreement: one from before that (there is no withdraw row; owner, 2026-11-25).
 * Agreeing here keeps the user signed in; signing out leads back to the sign-in page,
 * whose tap agrees too.
 */
/** The AI-data consent, in the brand's indigo like the rest of sign-in. */
export default function AiConsentScreen() {
  return (
    <BrandAccent>
      <AiConsent />
    </BrandAccent>
  );
}

function AiConsent() {
  const { token, user } = useAuth();
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { busy, agree, decline, deleteAccount } = useAiConsentActions();

  if (!token) return <Redirect href="/login" />;
  if (!needsAiDataConsent(user)) return <Redirect href="/" />;

  const gradientColors = [theme.primaryLight, theme.bg] as const;

  const actions = (
    <View style={s.actions}>
      <Button
        title={t("onboarding.consent_agree")}
        onPress={() => void agree()}
        size="lg"
        loading={busy === "agree"}
        loadingLabel={t("onboarding.consent_agree")}
        disabled={busy !== null}
        style={s.cta}
      />
      <Button
        title={t("onboarding.consent_decline")}
        onPress={() => void decline()}
        variant="ghost"
        loading={busy === "decline"}
        loadingLabel={t("onboarding.consent_decline")}
        disabled={busy !== null}
        style={s.cta}
      />
      <Button
        title={t("onboarding.consent_delete")}
        onPress={() => void deleteAccount()}
        variant="ghost"
        loading={busy === "delete"}
        loadingLabel={t("onboarding.consent_delete")}
        disabled={busy !== null}
        style={s.cta}
      />
    </View>
  );

  return (
    <LinearGradient colors={gradientColors} style={s.root}>
      <AuthScrollLayout justify="space-between" footer={actions}>
        <View>
          <View style={s.hero}>
            <View style={s.badge}>
              <Icon name="shield" size={IconSize.md} color={theme.onPrimary} />
            </View>
            <Text style={s.title} accessibilityRole="header">
              {t("onboarding.consent_title")}
            </Text>
            <Text style={s.intro}>{t("onboarding.consent_intro")}</Text>
          </View>

          <Pressable
            onPress={() => void openAllowedUrl(getLegalPrivacyUrl())}
            accessibilityRole="link"
            accessibilityLabel={t("onboarding.consent_privacy_link")}
            hitSlop={13}
            style={s.linkWrap}
          >
            <Text style={s.link}>{t("onboarding.consent_privacy_link")}</Text>
          </Pressable>
        </View>

      </AuthScrollLayout>
    </LinearGradient>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    root: { flex: 1 },
    hero: { alignItems: "center", marginBottom: Space.md },
    badge: {
      width: 56,
      height: 56,
      borderRadius: Radius.composer,
      backgroundColor: theme.primary,
      alignItems: "center",
      justifyContent: "center",
      marginBottom: Space.md,
    },
    title: { ...Type.display, color: theme.text, textAlign: "center" },
    intro: {
      ...Type.body,
      color: theme.textSecondary,
      marginTop: Space.xs,
      textAlign: "center",
    },
    linkWrap: { alignSelf: "center", marginTop: Space.xs },
    link: { ...Type.label, color: theme.primary, textDecorationLine: "underline" },
    actions: { gap: Space.xs, marginTop: Space.lg },
    cta: { alignSelf: "stretch" },
  });
}
