import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { Button } from "@/components/Button";
import { useAuth } from "@/contexts/AuthContext";
import { tap } from "@/lib/haptics";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

const FEATURES = [
  {
    icon: "chatbubble-ellipses-outline",
    titleKey: "onboarding.chat_title",
    bodyKey: "onboarding.chat_body",
  },
  {
    icon: "sparkles-outline",
    titleKey: "onboarding.remember_title",
    bodyKey: "onboarding.remember_body",
  },
  {
    icon: "school-outline",
    titleKey: "onboarding.learn_title",
    bodyKey: "onboarding.learn_body",
  },
] as const;

export default function Onboarding() {
  const { onboarded, completeOnboarding } = useAuth();
  const router = useRouter();
  const theme = useTheme();
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const s = useMemo(() => makeStyles(theme), [theme]);

  if (onboarded) return <Redirect href="/login" />;

  const gradientColors = [theme.primaryLight, theme.bg] as const;

  const finish = async () => {
    tap();
    await completeOnboarding();
    router.replace("/login");
  };

  return (
    <LinearGradient
      colors={gradientColors}
      style={[
        s.root,
        {
          paddingTop: Math.max(insets.top, 24),
          paddingBottom: Math.max(insets.bottom, 24),
        },
      ]}
    >
      <View style={s.hero}>
        <View style={s.badge}>
          <Text style={s.badgeStar}>✦</Text>
        </View>
        <Text style={s.title}>{t("onboarding.welcome")}</Text>
        <Text style={s.subtitle}>{t("onboarding.subtitle")}</Text>
      </View>

      <View style={s.features}>
        {FEATURES.map((f) => (
          <View key={f.titleKey} style={s.feature}>
            <View style={s.featureIcon}>
              <Icon name={f.icon as never} size={20} color={theme.primary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.featureTitle}>{t(f.titleKey)}</Text>
              <Text style={s.featureBody}>{t(f.bodyKey)}</Text>
            </View>
          </View>
        ))}
      </View>

      <Button title={t("onboarding.get_started")} onPress={() => void finish()} style={s.cta} />
    </LinearGradient>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    root: {
      flex: 1,
      paddingHorizontal: Space.lg,
      justifyContent: "center",
    },
    hero: { alignItems: "center", marginBottom: Space.xl + Space.xs },
    badge: {
      width: 72,
      height: 72,
      borderRadius: 24,
      backgroundColor: theme.primary,
      alignItems: "center",
      justifyContent: "center",
      marginBottom: Space.md,
    },
    badgeStar: { fontSize: 30, color: theme.onPrimary },
    title: {
      ...Type.display,
      color: theme.text,
      letterSpacing: -0.5,
    },
    subtitle: {
      ...Type.body,
      color: theme.textSecondary,
      marginTop: Space.xs,
      textAlign: "center",
    },
    features: { gap: 20, marginBottom: Space.xl + Space.xs },
    feature: { flexDirection: "row", alignItems: "flex-start", gap: 14 },
    featureIcon: {
      width: 40,
      height: 40,
      borderRadius: 12,
      backgroundColor: theme.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    featureTitle: {
      ...Type.body,
      fontWeight: "700",
      color: theme.text,
      marginBottom: 2,
    },
    featureBody: { ...Type.label, fontWeight: "400", color: theme.textSecondary, lineHeight: 20 },
    cta: {
      alignSelf: "stretch",
    },
  });
}
