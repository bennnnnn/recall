import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { CardShell } from "@/components/rich/CardShell";
import { SocialPlatform } from "@/lib/richBlocks";
import { C } from "@/constants/Colors";

type Props = { text: string; platform: SocialPlatform };

const META: Record<
  SocialPlatform,
  { label: string; icon: keyof typeof Ionicons.glyphMap; color: string }
> = {
  twitter: { label: "Post draft · X", icon: "logo-twitter", color: "#1DA1F2" },
  linkedin: {
    label: "Post draft · LinkedIn",
    icon: "logo-linkedin",
    color: "#0A66C2",
  },
  generic: {
    label: "Social post draft",
    icon: "megaphone-outline",
    color: C.primary,
  },
};

export function SocialPostCard({ text, platform }: Props) {
  const meta = META[platform];
  return (
    <CardShell
      label={meta.label}
      copyText={text}
      icon={meta.icon}
      accentColor={meta.color}
    >
      <View style={s.card}>
        <View style={s.avatar}>
          <Ionicons name="person" size={16} color={C.textSecondary} />
        </View>
        <View style={s.content}>
          <Text style={s.name}>You</Text>
          <Text style={s.post} selectable>
            {text}
          </Text>
        </View>
      </View>
    </CardShell>
  );
}

const s = StyleSheet.create({
  card: { flexDirection: "row", gap: 10, alignItems: "flex-start" },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: C.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  content: { flex: 1 },
  name: { fontSize: 14, fontWeight: "700", color: C.text, marginBottom: 4 },
  post: { fontSize: 16, lineHeight: 23, color: C.text },
});
