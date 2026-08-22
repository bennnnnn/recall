import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { useAuthToken } from "@/contexts/AuthContext";
import type { LessonFeedback } from "@/hooks/useLessonSession";
import { speakWord } from "@/lib/pronunciation";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  feedback: LessonFeedback;
  language?: string;
  onContinue: () => void;
};

export function LessonResultSheet({ feedback, language = "en", onContinue }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const token = useAuthToken();
  const s = makeStyles(theme);
  const word = feedback.word.trim();

  return (
    <View
      style={[s.sheet, feedback.correct ? s.sheetCorrect : s.sheetWrong]}
      accessibilityRole="summary"
      accessibilityLiveRegion="polite"
    >
      <View style={s.header}>
        <View style={s.status}>
          <Icon
            name={feedback.correct ? "checkmark-circle" : "close-circle"}
            size={22}
            color={feedback.correct ? theme.success : theme.danger}
          />
          <Text style={[s.statusText, { color: feedback.correct ? theme.success : theme.danger }]}>
            {feedback.correct ? t("quiz.correct") : t("quiz.incorrect")}
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
      {!feedback.correct ? <Text style={s.tryAgain}>{t("lesson.try_again")}</Text> : null}
      <Button title={t("lesson.continue")} onPress={onContinue} style={s.continue} />
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    sheet: {
      borderTopLeftRadius: Radius.sheet,
      borderTopRightRadius: Radius.sheet,
      paddingHorizontal: Space.lg,
      paddingTop: Space.md,
      paddingBottom: Space.lg,
      gap: Space.sm,
    },
    sheetCorrect: { backgroundColor: theme.successLight },
    sheetWrong: { backgroundColor: theme.dangerLight },
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
    tryAgain: {
      ...Type.secondary,
      color: theme.text,
    },
    continue: { marginTop: Space.xs },
  });
}
