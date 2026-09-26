import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Chip } from "@/ui/controls/Chip";
import type { Suggestion } from "@/lib/api";
import { Theme, useTheme } from "@/lib/theme";
import { Space } from "@/lib/space";
import { Type, Weight } from "@/lib/type";

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
            <Chip
              key={item.id}
              label={label}
              icon="lightbulb"
              numberOfLines={2}
              onPress={() => onSelect(item.text)}
              onLongPress={() => onDismiss(item.id)}
              accessibilityHint={t("chat.home.dismiss_suggestion")}
            />
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
      ...Weight.bold,
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
    },
    row: { flexDirection: "row", flexWrap: "wrap", gap: Space.xs },
  });
}
