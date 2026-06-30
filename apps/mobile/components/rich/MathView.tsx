import { StyleSheet, Text, View } from "react-native";

import { MathFormulaWebView } from "@/components/rich/MathFormulaWebView";
import { MathText } from "@/components/rich/MathText";
import { getPreviewWebView } from "@/lib/webView";
import { Theme, useTheme } from "@/lib/theme";

export function MathInline({ latex }: { latex: string }) {
  const theme = useTheme();
  return <MathText latex={latex.trim()} textColor={theme.text} />;
}

export function MathBlock({ latex }: { latex: string }) {
  const theme = useTheme();
  const s = makeStyles(theme);
  const trimmed = latex.trim();
  if (!trimmed) return null;

  const preview = getPreviewWebView();
  if (preview?.mode === "rnc") {
    return (
      <View style={s.wrap}>
        <MathFormulaWebView
          latex={trimmed}
          displayMode
          minHeight={48}
          textColor={theme.text}
          bgColor={theme.contentSurface}
        />
      </View>
    );
  }

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
