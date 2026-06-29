import { StyleSheet, Text, View } from "react-native";

import { MathText } from "@/components/rich/MathText";
import { Theme, useTheme } from "@/lib/theme";

export function MathInline({ latex }: { latex: string }) {
  const theme = useTheme();
  return <MathText latex={latex} textColor={theme.text} />;
}

export function MathBlock({ latex }: { latex: string }) {
  const theme = useTheme();
  const s = makeStyles(theme);
  const trimmed = latex.trim();
  if (!trimmed) return null;

  return (
    <View style={s.wrap}>
      <Text style={s.line} selectable>
        <MathText latex={trimmed} textColor={theme.text} />
      </Text>
    </View>
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    wrap: {
      marginVertical: 6,
      alignSelf: "stretch",
    },
    line: {
      textAlign: "center",
      lineHeight: 24,
    },
  });
