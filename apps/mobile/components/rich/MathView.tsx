import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { MathFormulaWebView } from "@/components/rich/MathFormulaWebView";
import { MathText } from "@/components/rich/MathText";
import { supportsInlineHtmlMathWebView } from "@/lib/mathWebViewSupport";
import { getPreviewWebView } from "@/lib/webView";
import { MATH_TALL_LINE_HEIGHT, splitMathLines } from "@/lib/mathText";
import { stripEmbeddedDollarWraps, stripRedundantDollarWrap } from "@/lib/mathFenceRetag";
import { useTheme } from "@/lib/theme";

export function MathInline({ latex }: { latex: string }) {
  const theme = useTheme();
  return <MathText latex={latex.trim()} textColor={theme.text} />;
}

export const MathBlock = React.memo(function MathBlock({ latex }: { latex: string }) {
  const theme = useTheme();
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
      <View style={styles.wrap}>
        {lines.map((line) => (
          <MathBlock key={`line:${line}`} latex={line} />
        ))}
      </View>
    );
  }

  const preview = getPreviewWebView();
  // RNC (dev client) or expo-dom (Expo Go) — both can host inline KaTeX HTML.
  if (supportsInlineHtmlMathWebView(preview?.mode)) {
    return (
      <View style={styles.wrap}>
        <MathFormulaWebView
          latex={trimmed}
          displayMode
          minHeight={48}
          textColor={theme.text}
          bgColor="transparent"
        />
      </View>
    );
  }

  // No WebView — native MathText can still outgrow the bubble; allow pan.
  return (
    <View style={[styles.wrap, styles.fallbackBox]}>
      <ScrollView
        horizontal
        nestedScrollEnabled
        showsHorizontalScrollIndicator
        contentContainerStyle={styles.lineScroll}
      >
        <Text style={styles.line} selectable>
          <MathText latex={trimmed} textColor={theme.text} />
        </Text>
      </ScrollView>
    </View>
  );
});

const styles = StyleSheet.create({
  wrap: {
    marginVertical: 8,
    alignSelf: "stretch",
  },
  fallbackBox: {
    paddingVertical: 10,
    paddingHorizontal: 4,
  },
  lineScroll: {
    flexGrow: 1,
    justifyContent: "center",
    minWidth: "100%",
    paddingHorizontal: 8,
  },
  line: {
    textAlign: "center",
    lineHeight: MATH_TALL_LINE_HEIGHT,
  },
});
