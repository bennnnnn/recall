import { useMemo } from "react";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/contexts/AuthContext";
import { tap } from "@/lib/haptics";
import { Theme, useTheme } from "@/lib/theme";

const FEATURES = [
  {
    icon: "school-outline",
    titleKey: "onboarding.learn_title",
    bodyKey: "onboarding.learn_body",
  },
  {
    icon: "calendar-outline",
    titleKey: "onboarding.organize_title",
    bodyKey: "onboarding.organize_body",
  },
  {
    icon: "sparkles-outline",
    titleKey: "onboarding.remember_title",
    bodyKey: "onboarding.remember_body",
  },
] as const;

export default function Onboarding() {
  const { onboarded, completeOnboarding } = useAuth();
  const router = useRouter();
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);

  if (onboarded) return <Redirect href="/login" />;

  const finish = async () => {
    tap();
    await completeOnboarding();
    router.replace("/login");
  };

  return (
    <View style={s.root}>
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
              <Ionicons name={f.icon as never} size={20} color={theme.primary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.featureTitle}>{t(f.titleKey)}</Text>
              <Text style={s.featureBody}>{t(f.bodyKey)}</Text>
            </View>
          </View>
        ))}
      </View>

      <Pressable style={s.cta} onPress={finish}>
        <Text style={s.ctaText}>{t("onboarding.get_started")}</Text>
      </Pressable>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    root: {
      flex: 1,
      backgroundColor: theme.bg,
      padding: 24,
      justifyContent: "center",
    },
    hero: { alignItems: "center", marginBottom: 40 },
    badge: {
      width: 72,
      height: 72,
      borderRadius: 24,
      backgroundColor: theme.primary,
      alignItems: "center",
      justifyContent: "center",
      marginBottom: 16,
    },
    badgeStar: { fontSize: 30, color: "#fff" },
    title: {
      fontSize: 28,
      fontWeight: "800",
      color: theme.text,
      letterSpacing: -0.5,
    },
    subtitle: {
      fontSize: 16,
      color: theme.textSecondary,
      marginTop: 6,
      textAlign: "center",
      lineHeight: 22,
    },
    features: { gap: 20, marginBottom: 40 },
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
      fontSize: 16,
      fontWeight: "700",
      color: theme.text,
      marginBottom: 2,
    },
    featureBody: { fontSize: 14, color: theme.textSecondary, lineHeight: 20 },
    cta: {
      backgroundColor: theme.primary,
      borderRadius: 16,
      paddingVertical: 16,
      alignItems: "center",
    },
    ctaText: { fontSize: 16, fontWeight: "700", color: "#fff" },
  });
}
