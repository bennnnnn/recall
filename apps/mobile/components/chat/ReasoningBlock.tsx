import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";

type Props = {
  content: string;
  streaming?: boolean;
};

export function ReasoningBlock({ content, streaming = false }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [expanded, setExpanded] = useState(false);
  const trimmed = content.trim();
  if (!trimmed) return null;

  const preview = trimmed.length > 120 && !expanded ? `${trimmed.slice(0, 120).trim()}…` : trimmed;

  return (
    <View style={s.wrap}>
      <Pressable
        style={s.header}
        onPress={() => setExpanded((value) => !value)}
        accessibilityRole="button"
        accessibilityState={{ expanded }}
      >
        <Ionicons name="sparkles-outline" size={14} color={theme.textSecondary} />
        <Text style={s.title}>{t("chat.reasoning_title")}</Text>
        {streaming ? <Text style={s.live}>{t("chat.reasoning_live")}</Text> : null}
        <Ionicons
          name={expanded ? "chevron-up" : "chevron-down"}
          size={14}
          color={theme.textTertiary}
          style={s.chevron}
        />
      </Pressable>
      <Text style={s.body}>{preview}</Text>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: {
      marginBottom: 8,
      paddingHorizontal: 12,
      paddingVertical: 10,
      borderRadius: 12,
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    header: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 6 },
    title: { fontSize: 12, fontWeight: "700", color: theme.textSecondary, flex: 1 },
    live: { fontSize: 11, color: theme.primary, fontWeight: "600" },
    chevron: { marginLeft: "auto" },
    body: { fontSize: 13, lineHeight: 18, color: theme.textSecondary },
  });
}
