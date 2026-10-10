import { Pressable, StyleSheet, View } from "react-native";

import { RichMathBody } from "@/components/rich/RichMathBody";
import { wrapSuggestionMath } from "@/features/suggestions/model/promptMath";
import { Theme, useTheme } from "@/lib/theme";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";

type Props = {
  prompts: string[];
  onSelect: (prompt: string) => void;
};

export function RelatedPromptLines({ prompts, onSelect }: Props) {
  const theme = useTheme();
  const s = makeStyles(theme);

  if (prompts.length === 0) return null;

  const lines = prompts.slice(0, 3);
  return (
    <View style={s.wrap}>
      {lines.map((prompt, index) => (
        <View key={prompt}>
          {index > 0 ? <View style={s.divider} testID="related-prompt-divider" /> : null}
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={prompt}
            onPress={() => onSelect(prompt)}
            style={s.row}
          >
            <Icon
              name="enter"
              size={IconSize.xs}
              color={theme.textSecondary}
              style={s.icon}
            />
            <View style={s.body}>
              <RichMathBody
                content={wrapSuggestionMath(prompt)}
                style={s.line}
                textColor={theme.textSecondary}
              />
            </View>
          </Pressable>
        </View>
      ))}
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: {
      paddingHorizontal: Space.md,
      paddingTop: Space.xxs,
      paddingBottom: Space.xs,
    },
    divider: {
      height: StyleSheet.hairlineWidth,
      backgroundColor: theme.separator,
      marginVertical: Space.xs,
    },
    row: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: Space.xs,
    },
    icon: {
      marginTop: 2,
    },
    body: {
      flex: 1,
    },
    line: {
      ...Type.secondary,
      color: theme.textSecondary,
    },
  });
}
