import { useEffect } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { useAuthToken } from "@/contexts/AuthContext";
import type { LessonFeedback } from "@/hooks/useLessonSession";
import { Motion, useReduceMotion } from "@/lib/motion";
import { speakWord } from "@/lib/pronunciation";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  feedback: LessonFeedback;
  language?: string;
  onContinue: () => void;
  saving?: boolean;
  error?: string | null;
};

export function LessonResultSheet({
  feedback,
  language = "en",
  onContinue,
  saving = false,
  error = null,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const token = useAuthToken();
  const s = makeStyles(theme);
  const word = feedback.word.trim();
  const reduceMotion = useReduceMotion();
  const translateY = useSharedValue(reduceMotion ? 0 : 120);
  const opacity = useSharedValue(reduceMotion ? 1 : 0);

  useEffect(() => {
    if (reduceMotion) {
      translateY.value = 0;
      opacity.value = 1;
      return;
    }
    translateY.value = withTiming(0, {
      duration: Motion.duration.snappy,
      easing: Motion.easing.out,
    });
    opacity.value = withTiming(1, {
      duration: Motion.duration.snappy,
      easing: Motion.easing.out,
    });
  }, [opacity, reduceMotion, translateY]);

  const sheetAnim = useAnimatedStyle(() => ({
    transform: [{ translateY: translateY.value }],
    opacity: opacity.value,
  }));

  return (
    <Animated.View
      style={[s.sheet, s.sheetCorrect, sheetAnim]}
      accessibilityRole="summary"
      accessibilityLiveRegion="polite"
    >
      <View style={s.header}>
        <View style={s.status}>
          <Icon name="checkmark-circle" size={22} color={theme.success} />
          <Text style={[s.statusText, { color: theme.success }]}>
            {t("quiz.correct")}
          </Text>
        </View>
        {word ? (
          <Pressable
            onPress={() => {
              void speakWord(word, {
                language: language === "en" ? "en-US" : language,
                token,
              });
            }}
            accessibilityRole="button"
            accessibilityLabel={t("quiz.pronunciation_unavailable_title")}
            hitSlop={8}
          >
            <Icon name="volume-medium-outline" size={22} color={theme.textSecondary} />
          </Pressable>
        ) : null}
      </View>
      {word ? <Text style={s.word}>{word}</Text> : null}
      {feedback.meaning ? <Text style={s.meaning}>{feedback.meaning}</Text> : null}
      {error ? (
        <Text style={s.saveError} accessibilityLiveRegion="assertive">
          {error}
        </Text>
      ) : null}
      <Button
        title={t("lesson.continue")}
        onPress={onContinue}
        loading={saving}
        disabled={saving}
        style={s.continue}
      />
    </Animated.View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    sheet: {
      position: "absolute",
      bottom: 0,
      left: 0,
      right: 0,
      borderTopLeftRadius: Radius.sheet,
      borderTopRightRadius: Radius.sheet,
      paddingHorizontal: Space.lg,
      paddingTop: Space.md,
      paddingBottom: Space.lg,
      gap: Space.sm,
    },
    sheetCorrect: { backgroundColor: theme.successLight },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
    },
    status: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
    },
    statusText: {
      ...Type.secondary,
      fontWeight: "700",
    },
    word: {
      fontSize: 22,
      fontWeight: "700",
      color: theme.text,
    },
    meaning: {
      ...Type.body,
      color: theme.textSecondary,
    },
    saveError: {
      ...Type.secondary,
      color: theme.danger,
      fontWeight: "600",
    },
    continue: { marginTop: Space.xs },
  });
}
