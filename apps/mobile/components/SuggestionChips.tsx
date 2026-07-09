import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import type { Suggestion } from "@/lib/api";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  suggestions: Suggestion[];
  onSelect: (prompt: string) => void;
  onDismiss: (id: string) => void;
};

export function SuggestionChips({ suggestions, onSelect, onDismiss }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = makeStyles(theme);

  if (suggestions.length === 0) return null;

  return (
    <View style={s.wrap}>
      <Text style={s.label}>{t("chat.suggestions")}</Text>
      <View style={s.row}>
        {suggestions.slice(0, 3).map((item) => {
          const label =
            item.text.length > 48 ? `${item.text.slice(0, 47).trimEnd()}…` : item.text;
          return (
            <Pressable
              key={item.id}
              style={s.chip}
              onPress={() => onSelect(item.text)}
              onLongPress={() => onDismiss(item.id)}
              accessibilityHint={t("chat.home.dismiss_suggestion")}
            >
              <Ionicons name="bulb-outline" size={14} color={theme.primary} />
              <Text style={s.chipText} numberOfLines={2}>
                {label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: {
      paddingHorizontal: 16,
      paddingTop: 4,
      paddingBottom: 8,
      gap: 8,
    },
    label: {
      fontSize: 12,
      fontWeight: "700",
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
    },
    row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    chip: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      maxWidth: "100%",
      backgroundColor: theme.surface,
      borderRadius: 999,
      paddingHorizontal: 12,
      paddingVertical: 8,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    chipText: { flexShrink: 1, fontSize: 13, color: theme.text, fontWeight: "500" },
  });
}
