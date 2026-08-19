import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { QuizChoice } from "@/lib/parseVocabQuiz";
import { tap } from "@/lib/haptics";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  choices: QuizChoice[];
  /** The correct letter from the quiz fence (for answer state coloring). */
  correctLetter?: QuizChoice["letter"] | null;
  disabled?: boolean;
  onSelect: (letter: QuizChoice["letter"]) => void;
};

export function VocabQuizChoices({
  choices,
  correctLetter,
  disabled = false,
  onSelect,
}: Props) {
  const theme = useTheme();
  const s = makeStyles(theme);
  const [selectedLetter, setSelectedLetter] = useState<QuizChoice["letter"] | null>(null);

  const answered = selectedLetter !== null && correctLetter !== null && correctLetter !== undefined;
  const isCorrect = answered && selectedLetter === correctLetter;

  return (
    <View style={s.row}>
      {choices.map((choice) => {
        const isSelected = choice.letter === selectedLetter;
        const isCorrectChoice = correctLetter === choice.letter;
        const showCorrect = answered && isCorrectChoice;
        const showWrong = answered && isSelected && !isCorrectChoice;

        let chipStyle = s.chip;
        if (showCorrect) chipStyle = s.chipCorrect;
        else if (showWrong) chipStyle = s.chipWrong;

        let letterStyle = s.letter;
        if (showCorrect) letterStyle = s.letterCorrect;
        else if (showWrong) letterStyle = s.letterWrong;

        return (
          <Pressable
            key={choice.letter}
            testID={`quiz-choice-${choice.letter}`}
            style={[chipStyle, disabled && s.chipDisabled]}
            disabled={disabled || answered}
            accessibilityRole="button"
            accessibilityLabel={`Answer ${choice.letter}: ${choice.text}`}
            accessibilityHint={
              answered
                ? undefined
                : `Select answer ${choice.letter}`
            }
            accessibilityState={{
              selected: isSelected,
              disabled: disabled || answered,
            }}
            onPress={() => {
              tap();
              setSelectedLetter(choice.letter);
              onSelect(choice.letter);
            }}
          >
            <Text style={letterStyle}>{choice.letter}</Text>
            <Text style={s.text} numberOfLines={3}>
              {choice.text}
            </Text>
            {showCorrect ? <Text style={s.checkmark}>✓</Text> : null}
            {showWrong ? <Text style={s.crossmark}>✕</Text> : null}
          </Pressable>
        );
      })}
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
    chipCorrect: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: 10,
      borderRadius: 14,
      borderWidth: 2,
      borderColor: theme.success,
      backgroundColor: theme.surface,
      paddingVertical: 12,
      paddingHorizontal: 12,
    },
    chipWrong: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: 10,
      borderRadius: 14,
      borderWidth: 2,
      borderColor: theme.danger,
      backgroundColor: theme.surface,
      paddingVertical: 12,
      paddingHorizontal: 12,
    },
    letter: {
      width: 22,
      fontSize: 15,
      fontWeight: "800",
      color: theme.primary,
    },
    letterCorrect: {
      width: 22,
      fontSize: 15,
      fontWeight: "800",
      color: theme.success,
    },
    letterWrong: {
      width: 22,
      fontSize: 15,
      fontWeight: "800",
      color: theme.danger,
    },
    text: {
      flex: 1,
      fontSize: 15,
      lineHeight: 21,
      color: theme.text,
    },
    checkmark: {
      fontSize: 16,
      fontWeight: "700",
      color: theme.success,
    },
    crossmark: {
      fontSize: 16,
      fontWeight: "700",
      color: theme.danger,
    },
  });
}
