import { useMemo } from "react";
import { StyleSheet, View } from "react-native";

import { RecallTypingIndicator } from "@/components/RecallTypingIndicator";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  quizVariant: "vocab" | "trivia";
};

export function DailyQuizLoadingRow(_props: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={s.row}>
      <View style={s.bubble}>
        <RecallTypingIndicator />
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
      paddingVertical: 4,
    },
  });
}
