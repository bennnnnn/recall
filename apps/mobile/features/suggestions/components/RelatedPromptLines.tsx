import { Pressable, StyleSheet, View } from "react-native";

import { RichMathBody } from "@/components/rich/RichMathBody";
import { suggestionToSend, wrapSuggestionMath } from "@/features/suggestions/model/promptMath";
import { Theme, useTheme } from "@/lib/theme";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";

type Props = {
  prompts: string[];
  onSelect: (prompt: string) => void;
};

/**
 * Follow-up questions under the latest reply: a short list, one tappable row
 * per question, each opened by a 1pt rule so the rows read as a list.
 */
export function RelatedPromptLines({ prompts, onSelect }: Props) {
  const theme = useTheme();
  const s = makeStyles(theme);

  if (prompts.length === 0) return null;

  const lines = prompts
    .map((prompt) => suggestionToSend(prompt))
    .filter((prompt): prompt is string => prompt !== null)
    .slice(0, 3);
  if (lines.length === 0) return null;
  return (
    <View style={s.wrap}>
      {lines.map((prompt) => (
        <View key={prompt}>
          <View style={s.divider} testID="related-prompt-divider" />
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={prompt}
            onPress={() => onSelect(prompt)}
            style={({ pressed }) => [s.row, pressed && s.rowPressed]}
          >
            <Icon name="enter" size={IconSize.xs} color={theme.textTertiary} />
            <View style={s.body}>
              <RichMathBody
                content={wrapSuggestionMath(prompt)}
                style={s.line}
                textColor={theme.text}
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
      marginHorizontal: Space.md,
      marginTop: Space.xs,
      marginBottom: Space.xs,
    },
    // 1pt, not a hairline: a hairline in `separator` all but vanishes on white.
    divider: {
      height: 1,
      backgroundColor: theme.separator,
    },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      minHeight: Space.minTouch,
      paddingVertical: Space.xs,
    },
    rowPressed: {
      backgroundColor: theme.pressed,
    },
    body: {
      flex: 1,
    },
    line: {
      ...Type.secondary,
      color: theme.text,
    },
  });
}
