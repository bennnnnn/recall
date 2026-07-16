import React from "react";
import { StyleSheet, Text, View } from "react-native";

import { MathFormulaWebView } from "@/components/rich/MathFormulaWebView";
import { MathText } from "@/components/rich/MathText";
import { getPreviewWebView } from "@/lib/webView";
import { splitMathLines } from "@/lib/mathText";
import { stripEmbeddedDollarWraps, stripRedundantDollarWrap } from "@/lib/mathFenceRetag";
import { Theme, useTheme } from "@/lib/theme";

export function MathInline({ latex }: { latex: string }) {
  const theme = useTheme();
  return <MathText latex={latex.trim()} textColor={theme.text} />;
}

export const MathBlock = React.memo(function MathBlock({ latex }: { latex: string }) {
  const theme = useTheme();
  const s = makeStyles(theme);
  const trimmed = stripEmbeddedDollarWraps(stripRedundantDollarWrap(latex.trim()));
  if (!trimmed) return null;

  // A fence body with multiple independent equations (one per line) must
  // render each as its own block — a single render call concatenates every
  // line into one expression with no separator. splitMathLines is
  // environment-aware: it returns the whole body as one entry when it
  // contains a \begin{…} (aligned/cases/matrix/…), so multi-line
  // environments render as a single KaTeX block instead of being shattered
  // into per-row parse errors.
  const lines = splitMathLines(trimmed);
  if (lines.length > 1) {
    return (
      <View style={s.wrap}>
        {lines.map((line) => (
          <MathBlock key={`line:${line}`} latex={line} />
        ))}
      </View>
    );
  }

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
});

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
