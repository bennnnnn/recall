import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { tap } from "@/lib/haptics";
import type { QuizChoice } from "@/lib/parseVocabQuiz";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  choices: QuizChoice[];
  correctLetter?: QuizChoice["letter"] | null;
  disabled?: boolean;
  resetToken?: number | string;
  onSelect: (letter: QuizChoice["letter"]) => void;
};

export function LessonQuizCards({
  choices,
  correctLetter,
  disabled = false,
  resetToken = 0,
  onSelect,
}: Props) {
  const theme = useTheme();
  const s = makeStyles(theme);
  const [selectedLetter, setSelectedLetter] = useState<QuizChoice["letter"] | null>(null);

  useEffect(() => {
    setSelectedLetter(null);
  }, [resetToken]);

  const answered = selectedLetter != null && correctLetter != null;

  return (
    <View style={s.grid}>
      {choices.map((choice) => {
        const isSelected = choice.letter === selectedLetter;
        const isCorrectChoice = correctLetter === choice.letter;
        const showCorrect = answered && isCorrectChoice;
        const showWrong = answered && isSelected && !isCorrectChoice;
        return (
          <Pressable
            key={choice.letter}
            testID={`lesson-choice-${choice.letter}`}
            style={[
              s.card,
              showCorrect && s.cardCorrect,
              showWrong && s.cardWrong,
              disabled && s.cardDisabled,
            ]}
            disabled={disabled || answered}
            accessibilityRole="button"
            accessibilityLabel={`${choice.letter}: ${choice.text}`}
            accessibilityState={{ selected: isSelected, disabled: disabled || answered }}
            onPress={() => {
              tap();
              setSelectedLetter(choice.letter);
              onSelect(choice.letter);
            }}
          >
            <Text style={[s.letter, showCorrect && s.letterCorrect, showWrong && s.letterWrong]}>
              {choice.letter}
            </Text>
            <Text style={s.text}>{choice.text}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    grid: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: Space.sm,
    },
    card: {
      width: "47%",
      flexGrow: 1,
      minHeight: 112,
      borderRadius: Radius.xl,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      backgroundColor: theme.surface,
      padding: Space.md,
      gap: Space.xs,
    },
    cardCorrect: {
      borderWidth: 2,
      borderColor: theme.success,
      backgroundColor: theme.successLight,
    },
    cardWrong: {
      borderWidth: 2,
      borderColor: theme.danger,
      backgroundColor: theme.dangerLight,
    },
    cardDisabled: { opacity: 0.55 },
    letter: {
      ...Type.caption,
      fontWeight: "800",
      color: theme.primary,
    },
    letterCorrect: { color: theme.success },
    letterWrong: { color: theme.danger },
    text: {
      ...Type.body,
      color: theme.text,
    },
  });
}
