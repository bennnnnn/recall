import { useEffect, useRef, useState } from "react";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";
import type { ParsedVocabQuiz } from "@/lib/parseVocabQuiz";
import { cleanQuizWord } from "@/lib/parseVocabQuiz";
import { partOfSpeechLabel } from "@/lib/languageLevels";
import { speakWord } from "@/lib/pronunciation";

type Props = {
  quiz: ParsedVocabQuiz;
  disabled?: boolean;
  language?: string;
  initialSelected?: "A" | "B" | "C" | "D" | null;
  onSelect?: (letter: "A" | "B" | "C" | "D") => void;
};

const SUCCESS = "#16a34a";
const SUCCESS_LIGHT = "#dcfce7";

export function VocabQuizChoices({
  quiz,
  disabled,
  language = "en",
  initialSelected = null,
  onSelect,
}: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = makeStyles(theme);
  const warnedSpeech = useRef(false);
  const [selected, setSelected] = useState<"A" | "B" | "C" | "D" | null>(
    initialSelected,
  );

  useEffect(() => {
    if (initialSelected != null) {
      setSelected(initialSelected);
    }
  }, [initialSelected]);

  const displayWord = cleanQuizWord(quiz.word);
  const questionText = quiz.question?.trim() || t("quiz.question_default");
  const revealResult = selected != null && quiz.correct != null;

  const handleSpeak = async () => {
    const result = await speakWord(displayWord, {
      language: language === "en" ? "en-US" : language,
    });
    if (!result.ok && result.reason === "unavailable" && !warnedSpeech.current) {
      warnedSpeech.current = true;
      Alert.alert(
        t("quiz.pronunciation_unavailable_title"),
        t("quiz.pronunciation_unavailable_body"),
      );
    }
  };

  const handleChoice = (letter: "A" | "B" | "C" | "D") => {
    if (disabled || selected) return;
    setSelected(letter);
    onSelect?.(letter);
  };

  const choiceState = (letter: "A" | "B" | "C" | "D") => {
    if (!revealResult) {
      return selected === letter ? "selected" : "idle";
    }
    if (letter === quiz.correct) return "correct";
    if (letter === selected) return "wrong";
    return "idle";
  };

  return (
    <View style={s.wrap}>
      <View style={s.card}>
        {quiz.partOfSpeech ? (
          <View style={s.posBadge}>
            <Text style={s.pos}>{partOfSpeechLabel(quiz.partOfSpeech)}</Text>
          </View>
        ) : null}
        <View style={s.wordRow}>
          <Text style={s.word}>{displayWord}</Text>
          <Pressable style={s.speakBtn} onPress={() => void handleSpeak()} hitSlop={8}>
            <Ionicons name="volume-high-outline" size={22} color={theme.primary} />
          </Pressable>
        </View>
        <Text style={s.question}>{questionText}</Text>
      </View>
      <View style={s.choices}>
        {quiz.choices.map((choice) => {
          const state = choiceState(choice.letter);
          const isSelected = state === "selected" || state === "wrong";
          const isCorrect = state === "correct";
          const isWrong = state === "wrong";
          return (
            <Pressable
              key={choice.letter}
              style={({ pressed }) => [
                s.choice,
                isSelected && s.choiceSelected,
                isCorrect && s.choiceCorrect,
                isWrong && s.choiceWrong,
                pressed && !disabled && !selected && s.choicePressed,
                disabled && !isSelected && !isCorrect && s.choiceDisabled,
              ]}
              disabled={disabled || selected != null}
              onPress={() => handleChoice(choice.letter)}
            >
              <View
                style={[
                  s.choiceLetter,
                  isSelected && s.choiceLetterSelected,
                  isCorrect && s.choiceLetterCorrect,
                  isWrong && s.choiceLetterWrong,
                ]}
              >
                <Text
                  style={[
                    s.choiceLetterText,
                    (isSelected || isCorrect || isWrong) && s.choiceLetterTextSelected,
                  ]}
                >
                  {choice.letter}
                </Text>
              </View>
              <Text
                style={[
                  s.choiceText,
                  (isSelected || isCorrect) && s.choiceTextSelected,
                  isWrong && s.choiceTextWrong,
                ]}
              >
                {choice.text}
              </Text>
              {isCorrect ? (
                <Ionicons name="checkmark-circle" size={20} color={SUCCESS} />
              ) : isWrong ? (
                <Ionicons name="close-circle" size={20} color={theme.danger} />
              ) : isSelected ? (
                <Ionicons name="checkmark-circle" size={20} color={theme.primary} />
              ) : null}
            </Pressable>
          );
        })}
      </View>
      {revealResult ? (
        <Text style={[s.feedback, selected === quiz.correct ? s.feedbackOk : s.feedbackBad]}>
          {selected === quiz.correct ? t("quiz.correct") : t("quiz.incorrect")}
        </Text>
      ) : null}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: { gap: 12, marginTop: 8 },
    card: {
      position: "relative",
      backgroundColor: t.surface,
      borderRadius: 16,
      borderWidth: 1,
      borderColor: t.border,
      paddingHorizontal: 18,
      paddingVertical: 22,
      alignItems: "center",
      minHeight: 96,
    },
    posBadge: {
      position: "absolute",
      top: 10,
      right: 10,
      backgroundColor: t.primaryLight,
      borderRadius: 999,
      paddingHorizontal: 8,
      paddingVertical: 3,
    },
    pos: {
      fontSize: 10,
      fontWeight: "800",
      color: t.primary,
      textTransform: "uppercase",
      letterSpacing: 0.6,
    },
    wordRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
    },
    word: {
      fontSize: 28,
      fontWeight: "800",
      color: t.text,
      textAlign: "center",
    },
    question: {
      marginTop: 10,
      fontSize: 15,
      lineHeight: 21,
      color: t.textSecondary,
      textAlign: "center",
    },
    speakBtn: {
      width: 36,
      height: 36,
      borderRadius: 18,
      backgroundColor: t.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    choices: { gap: 8 },
    choice: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      borderRadius: 14,
      borderWidth: 1.5,
      borderColor: t.border,
      backgroundColor: t.surface,
      paddingHorizontal: 14,
      paddingVertical: 12,
    },
    choicePressed: {
      borderColor: t.primary,
      backgroundColor: t.primaryLight,
      transform: [{ scale: 0.985 }],
    },
    choiceSelected: {
      borderColor: t.primary,
      backgroundColor: t.primaryLight,
    },
    choiceCorrect: {
      borderColor: SUCCESS,
      backgroundColor: SUCCESS_LIGHT,
    },
    choiceWrong: {
      borderColor: t.danger,
      backgroundColor: t.dangerLight,
    },
    choiceDisabled: { opacity: 0.55 },
    choiceLetter: {
      width: 28,
      height: 28,
      borderRadius: 14,
      backgroundColor: t.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    choiceLetterSelected: {
      backgroundColor: t.primary,
    },
    choiceLetterCorrect: {
      backgroundColor: SUCCESS,
    },
    choiceLetterWrong: {
      backgroundColor: t.danger,
    },
    choiceLetterText: {
      color: t.primary,
      fontSize: 14,
      fontWeight: "800",
    },
    choiceLetterTextSelected: {
      color: "#fff",
    },
    choiceText: {
      flex: 1,
      fontSize: 15,
      lineHeight: 21,
      color: t.text,
    },
    choiceTextSelected: {
      fontWeight: "700",
      color: t.text,
    },
    choiceTextWrong: {
      color: t.danger,
    },
    feedback: {
      fontSize: 14,
      fontWeight: "600",
      textAlign: "center",
    },
    feedbackOk: {
      color: SUCCESS,
    },
    feedbackBad: {
      color: t.danger,
    },
  });
}
