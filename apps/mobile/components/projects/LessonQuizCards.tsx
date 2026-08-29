/* eslint-disable react-hooks/immutability -- Reanimated shared values are mutated on the UI thread by design */
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withSequence,
  withSpring,
  withTiming,
} from "react-native-reanimated";

import { notifySuccess, notifyWarning } from "@/lib/haptics";
import { useReduceMotion } from "@/lib/motion";
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
  onWrongAnswer?: () => void;
};

export function LessonQuizCards({
  choices,
  correctLetter,
  disabled = false,
  resetToken = 0,
  onSelect,
  onWrongAnswer,
}: Props) {
  const theme = useTheme();
  const s = makeStyles(theme);
  const [selectedLetter, setSelectedLetter] = useState<QuizChoice["letter"] | null>(null);
  const [wrongLetter, setWrongLetter] = useState<QuizChoice["letter"] | null>(null);

  useEffect(() => {
    setSelectedLetter(null);
    setWrongLetter(null);
  }, [resetToken]);

  const answeredCorrectly =
    selectedLetter != null && correctLetter != null && selectedLetter === correctLetter;

  return (
    <View style={s.list}>
      {choices.map((choice) => {
        const isSelected = choice.letter === selectedLetter;
        const isCorrectChoice = correctLetter === choice.letter;
        const showCorrect = answeredCorrectly && isCorrectChoice;
        const showWrong = wrongLetter === choice.letter && !answeredCorrectly;
        const isLocked = disabled || answeredCorrectly;
        return (
          <QuizCard
            key={choice.letter}
            choice={choice}
            isCorrect={correctLetter === choice.letter}
            showCorrect={showCorrect}
            showWrong={showWrong}
            disabled={isLocked}
            isSelected={isSelected}
            styles={s}
            onPress={() => {
              const correct = correctLetter != null && choice.letter === correctLetter;
              if (correct) {
                notifySuccess();
                setWrongLetter(null);
                setSelectedLetter(choice.letter);
                onSelect(choice.letter);
              } else {
                notifyWarning();
                setWrongLetter(choice.letter);
                onWrongAnswer?.();
              }
            }}
          />
        );
      })}
    </View>
  );
}

function QuizCard({
  choice,
  isCorrect,
  showCorrect,
  showWrong,
  disabled,
  isSelected,
  styles: s,
  onPress,
}: {
  choice: QuizChoice;
  isCorrect: boolean;
  showCorrect: boolean;
  showWrong: boolean;
  disabled: boolean;
  isSelected: boolean;
  styles: ReturnType<typeof makeStyles>;
  onPress: () => void;
}) {
  const scale = useSharedValue(1);
  const shakeX = useSharedValue(0);
  const reduceMotion = useReduceMotion();
  const cardAnim = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }, { translateX: shakeX.value }],
  }));

  const handlePress = () => {
    if (!reduceMotion) {
      if (isCorrect) {
        scale.value = withSequence(
          withSpring(1.06, { damping: 12, stiffness: 200 }),
          withSpring(1, { damping: 14, stiffness: 200 }),
        );
      } else {
        scale.value = withSequence(
          withSpring(0.94, { damping: 14, stiffness: 300 }),
          withSpring(1, { damping: 14, stiffness: 200 }),
        );
        shakeX.value = withSequence(
          withTiming(-8, { duration: 50 }),
          withTiming(8, { duration: 50 }),
          withTiming(-6, { duration: 50 }),
          withTiming(6, { duration: 50 }),
          withTiming(-3, { duration: 40 }),
          withTiming(0, { duration: 40 }),
        );
      }
    }
    onPress();
  };

  return (
    <Animated.View style={[s.cardWrap, cardAnim]}>
      <Pressable
        testID={`lesson-choice-${choice.letter}`}
        style={[
          s.card,
          showCorrect && s.cardCorrect,
          showWrong && s.cardWrong,
          disabled && !showWrong && s.cardDisabled,
        ]}
        disabled={disabled}
        accessibilityRole="button"
        accessibilityState={{ selected: isSelected, disabled }}
        accessibilityLabel={`${choice.letter}. ${choice.text}`}
        onPress={handlePress}
      >
        <View style={s.row}>
          <Text style={s.letter}>{choice.letter}</Text>
          <Text style={s.text}>{choice.text}</Text>
        </View>
      </Pressable>
    </Animated.View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    list: {
      gap: Space.sm,
    },
    cardWrap: {
      width: "100%",
    },
    card: {
      minHeight: 64,
      borderRadius: Radius.lg,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      backgroundColor: theme.surface,
      paddingVertical: Space.md,
      paddingHorizontal: Space.lg,
      justifyContent: "center",
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
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.md,
    },
    letter: {
      ...Type.body,
      fontWeight: "800",
      color: theme.primary,
      minWidth: 22,
    },
    text: {
      ...Type.body,
      color: theme.text,
      flex: 1,
    },
  });
}
