/* eslint-disable react-hooks/immutability -- Reanimated shared values are mutated on the UI thread by design */
import { Pressable, StyleSheet, Text, View } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withSequence,
  withSpring,
  withTiming,
} from "react-native-reanimated";

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
  selectedLetter?: QuizChoice["letter"] | null;
  textScale?: number;
};

export function LessonQuizCards({
  choices,
  correctLetter,
  disabled = false,
  selectedLetter = null,
  textScale = 1,
  onSelect,
}: Props) {
  const theme = useTheme();
  const s = makeStyles(theme, textScale);
  const answeredCorrectly =
    selectedLetter != null && correctLetter != null && selectedLetter === correctLetter;

  return (
    <View style={s.list}>
      {choices.map((choice) => {
        const isSelected = choice.letter === selectedLetter;
        const isCorrectChoice = correctLetter === choice.letter;
        const showCorrect = answeredCorrectly && isCorrectChoice;
        const showWrong = selectedLetter === choice.letter && !answeredCorrectly;
        const recede = answeredCorrectly && !showCorrect;
        const isLocked = disabled || answeredCorrectly;
        return (
          <QuizCard
            key={choice.letter}
            choice={choice}
            isCorrect={isCorrectChoice}
            showCorrect={showCorrect}
            showWrong={showWrong}
            recede={recede}
            disabled={isLocked}
            isSelected={isSelected}
            styles={s}
            onPress={() => {
              onSelect(choice.letter);
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
  recede,
  disabled,
  isSelected,
  styles: s,
  onPress,
}: {
  choice: QuizChoice;
  isCorrect: boolean;
  showCorrect: boolean;
  showWrong: boolean;
  recede: boolean;
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
          recede && s.cardRecede,
          disabled && !showWrong && !showCorrect && !recede && s.cardDisabled,
        ]}
        disabled={disabled}
        accessibilityRole="button"
        accessibilityState={{ selected: isSelected, disabled }}
        accessibilityLabel={choice.text}
        onPress={handlePress}
      >
        <Text style={s.text}>{choice.text}</Text>
      </Pressable>
    </Animated.View>
  );
}

function makeStyles(theme: Theme, scale: number) {
  const n = (size: number) => Math.round(size * scale);
  return StyleSheet.create({
    list: {
      gap: Space.sm,
    },
    cardWrap: {
      width: "100%",
    },
    card: {
      minHeight: 64,
      borderRadius: Radius.xl,
      backgroundColor: theme.surface,
      paddingVertical: Space.md,
      paddingHorizontal: Space.md,
      justifyContent: "center",
    },
    cardCorrect: {
      backgroundColor: theme.successLight,
    },
    cardWrong: {
      backgroundColor: theme.dangerLight,
    },
    cardRecede: {
      opacity: 0.4,
    },
    cardDisabled: { opacity: 0.55 },
    text: {
      ...Type.body,
      fontSize: n(20),
      lineHeight: n(28),
      color: theme.text,
    },
  });
}
