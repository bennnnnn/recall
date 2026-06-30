import { useMemo } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { PRIVACY_POLICY } from "@/lib/privacyPolicy";
import { Theme, useTheme } from "@/lib/theme";

export default function PrivacyScreen() {
  const insets = useSafeAreaInsets();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  const sections = PRIVACY_POLICY.split("\n").filter(Boolean);

  const renderLine = (line: string, i: number) => {
    if (line.startsWith("# ")) {
      return (
        <Text key={i} style={s.h1}>
          {line.slice(2)}
        </Text>
      );
    }
    if (line.startsWith("## ")) {
      return (
        <Text key={i} style={s.h2}>
          {line.slice(3)}
        </Text>
      );
    }
    if (line.startsWith("- ")) {
      return (
        <View key={i} style={s.bulletRow}>
          <Text style={s.bullet}>{"•"}</Text>
          <Text style={s.bulletText}>{line.slice(2)}</Text>
        </View>
      );
    }
    return (
      <Text key={i} style={s.body}>
        {line}
      </Text>
    );
  };

  return (
    <ScrollView
      style={s.root}
      contentContainerStyle={[
        s.content,
        { paddingBottom: insets.bottom + 40 },
      ]}
      showsVerticalScrollIndicator={false}
    >
      {sections.map(renderLine)}
    </ScrollView>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: theme.bg },
    content: { paddingHorizontal: 20, paddingTop: 8 },
    h1: {
      fontSize: 22,
      fontWeight: "700",
      color: theme.text,
      marginBottom: 12,
      marginTop: 8,
    },
    h2: {
      fontSize: 17,
      fontWeight: "700",
      color: theme.text,
      marginBottom: 8,
      marginTop: 20,
    },
    body: { fontSize: 15, lineHeight: 22, color: theme.text, marginBottom: 8 },
    bulletRow: { flexDirection: "row", gap: 8, marginBottom: 4, paddingLeft: 4 },
    bullet: { fontSize: 15, color: theme.primary, lineHeight: 22 },
    bulletText: { flex: 1, fontSize: 15, lineHeight: 22, color: theme.text },
  });
}
