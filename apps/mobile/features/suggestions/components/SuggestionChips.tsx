import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import type { Suggestion } from "@/lib/api";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";

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
              accessibilityRole="button"
              accessibilityLabel={label}
              accessibilityHint={t("chat.home.dismiss_suggestion")}
            >
              <Icon name="bulb-outline" size={14} color={theme.primary} />
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
      paddingHorizontal: Space.md,
      paddingTop: Space.xxs,
      paddingBottom: Space.xs,
      gap: Space.xs,
    },
    label: {
      ...Type.caption,
      fontWeight: "700",
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
    },
    row: { flexDirection: "row", flexWrap: "wrap", gap: Space.xs },
    chip: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      maxWidth: "100%",
      minHeight: 44,
      backgroundColor: theme.surface,
      borderRadius: Radius.full,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xs,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    chipText: { flexShrink: 1, ...Type.compact, color: theme.text, fontWeight: "500" },
  });
}
