import { Pressable, StyleSheet, Text, View } from "react-native";

import type { QuizChoice } from "@/lib/parseVocabQuiz";
import { tap } from "@/lib/haptics";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  choices: QuizChoice[];
  disabled?: boolean;
  onSelect: (letter: QuizChoice["letter"]) => void;
};

export function VocabQuizChoices({ choices, disabled = false, onSelect }: Props) {
  const theme = useTheme();
  const s = makeStyles(theme);

  return (
    <View style={s.row}>
      {choices.map((choice) => (
        <Pressable
          key={choice.letter}
          style={[s.chip, disabled && s.chipDisabled]}
          disabled={disabled}
          onPress={() => {
            tap();
            onSelect(choice.letter);
          }}
        >
          <Text style={s.letter}>{choice.letter}</Text>
          <Text style={s.text} numberOfLines={3}>
            {choice.text}
          </Text>
        </Pressable>
      ))}
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    row: { gap: 8, marginTop: 10 },
    chip: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: 10,
      borderRadius: 14,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      backgroundColor: theme.surface,
      paddingVertical: 12,
      paddingHorizontal: 12,
    },
    chipDisabled: { opacity: 0.45 },
    letter: {
      width: 22,
      fontSize: 15,
      fontWeight: "800",
      color: theme.primary,
    },
    text: {
      flex: 1,
      fontSize: 15,
      lineHeight: 21,
      color: theme.text,
    },
  });
}
