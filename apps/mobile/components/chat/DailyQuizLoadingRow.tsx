import { useMemo } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";

type Props = {
  quizVariant: "vocab" | "trivia";
};

export function DailyQuizLoadingRow({ quizVariant }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const loadingKey =
    quizVariant === "trivia" ? "daily_quiz.loading_trivia" : "daily_quiz.loading_vocab";

  return (
    <View style={s.row}>
      <View style={s.bubble}>
        <ActivityIndicator color={theme.primary} />
        <Text style={s.hint}>{t(loadingKey)}</Text>
      </View>
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    row: { marginVertical: 4, paddingHorizontal: 16, alignItems: "stretch" },
    bubble: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingVertical: 8,
    },
    hint: { fontSize: 15, color: t.textSecondary },
  });
}
