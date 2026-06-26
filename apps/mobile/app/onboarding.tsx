import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Redirect, useRouter } from "expo-router";

import { C } from "@/constants/Colors";
import { useAuth } from "@/contexts/AuthContext";

const FEATURES = [
  {
    icon: "sparkles-outline",
    title: "Remembers you",
    body: "Recall learns your preferences, projects, and context across chats.",
  },
  {
    icon: "flash-outline",
    title: "Multiple models",
    body: "Switch between fast and smart models — or let Auto pick for each message.",
  },
  {
    icon: "lock-closed-outline",
    title: "Private by default",
    body: "Sign in with Google. Export or delete your data anytime.",
  },
] as const;

export default function Onboarding() {
  const { onboarded, completeOnboarding } = useAuth();
  const router = useRouter();

  if (onboarded) return <Redirect href="/login" />;

  const finish = async () => {
    await completeOnboarding();
    router.replace("/login");
  };

  return (
    <View style={s.root}>
      <View style={s.hero}>
        <View style={s.badge}>
          <Text style={s.badgeStar}>✦</Text>
        </View>
        <Text style={s.title}>Welcome to Recall</Text>
        <Text style={s.subtitle}>Your AI that remembers you.</Text>
      </View>

      <View style={s.features}>
        {FEATURES.map((f) => (
          <View key={f.title} style={s.feature}>
            <View style={s.featureIcon}>
              <Ionicons name={f.icon as never} size={20} color={C.primary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.featureTitle}>{f.title}</Text>
              <Text style={s.featureBody}>{f.body}</Text>
            </View>
          </View>
        ))}
      </View>

      <Pressable style={s.cta} onPress={finish}>
        <Text style={s.ctaText}>Get started</Text>
      </Pressable>
    </View>
  );
}

const s = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: C.bg,
    padding: 24,
    justifyContent: "center",
  },
  hero: { alignItems: "center", marginBottom: 40 },
  badge: {
    width: 72,
    height: 72,
    borderRadius: 24,
    backgroundColor: C.primary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  badgeStar: { fontSize: 30, color: "#fff" },
  title: {
    fontSize: 28,
    fontWeight: "800",
    color: C.text,
    letterSpacing: -0.5,
  },
  subtitle: { fontSize: 16, color: C.textSecondary, marginTop: 6 },
  features: { gap: 20, marginBottom: 40 },
  feature: { flexDirection: "row", alignItems: "flex-start", gap: 14 },
  featureIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: C.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  featureTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: C.text,
    marginBottom: 2,
  },
  featureBody: { fontSize: 14, color: C.textSecondary, lineHeight: 20 },
  cta: {
    backgroundColor: C.primary,
    borderRadius: 16,
    paddingVertical: 16,
    alignItems: "center",
  },
  ctaText: { fontSize: 16, fontWeight: "700", color: "#fff" },
});
