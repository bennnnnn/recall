import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Chip } from "@/ui/controls/Chip";
import { Theme, useTheme } from "@/lib/theme";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";

type Props = {
  prompts: string[];
  onSelect: (prompt: string) => void;
};

const LABEL_LIMIT = 48;

export function RelatedPromptChips({ prompts, onSelect }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = makeStyles(theme);

  if (prompts.length === 0) return null;

  return (
    <View style={s.wrap}>
      <Text style={s.label}>{t("chat.suggestions")}</Text>
      <View style={s.row}>
        {prompts.slice(0, 3).map((prompt) => {
          const label =
            prompt.length > LABEL_LIMIT
              ? `${prompt.slice(0, LABEL_LIMIT - 1).trimEnd()}…`
              : prompt;
          return (
            <Chip
              key={prompt}
              label={label}
              icon="lightbulb"
              numberOfLines={2}
              onPress={() => onSelect(prompt)}
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
    label: { ...Type.overline, color: theme.textTertiary },
    row: { flexDirection: "row", flexWrap: "wrap", gap: Space.xs },
  });
}
