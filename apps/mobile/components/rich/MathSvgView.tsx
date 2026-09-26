import React, { useEffect, useMemo, useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SvgXml } from "react-native-svg";

import { MathText } from "@/components/rich/MathText";
import { latexToSvgMath, peekSvgMath, type SvgMathResult } from "@/lib/math/svgMath";
import { latexHasNestedMathView, MATH_TALL_LINE_HEIGHT } from "@/lib/math/text";
import { Space } from "@/lib/space";

/**
 * MathJax metrics: the SVG viewBox runs 1000 units per em and 1ex ≈ 0.442em
 * (measured from MathJax output). Render display math at the same 20px em the
 * retired KaTeX WebView used.
 */
const EX_PX = 20 * 0.442;

type Props = {
  latex: string;
  textColor: string;
  minHeight?: number;
};

/**
 * Display-math formula as a native SVG — no WebView, no postMessage height
 * round-trip, no stream flicker. Falls back to readable MathText when MathJax
 * cannot parse the input (mirrors the old no-WebView fallback box).
 */
export const MathSvgView = React.memo(function MathSvgView({
  latex,
  textColor,
  minHeight = 48,
}: Props) {
  const [result, setResult] = useState<SvgMathResult | null | undefined>(() =>
    peekSvgMath(latex, true),
  );

  useEffect(() => {
    const peeked = peekSvgMath(latex, true);
    if (peeked !== undefined) {
      setResult(peeked);
      return;
    }
    let live = true;
    setResult(undefined);
    void latexToSvgMath(latex, true).then((next) => {
      if (live) setResult(next);
    });
    return () => {
      live = false;
    };
  }, [latex]);

  // react-native-svg does not resolve currentColor — substitute the theme color.
  const xml = useMemo(
    () => (result ? result.svg.split("currentColor").join(textColor) : null),
    [result, textColor],
  );

  if (result === undefined) {
    return <View style={[styles.wrap, { minHeight }]} testID="math-svg-loading" />;
  }

  if (result === null || xml == null) {
    const hasNestedView = latexHasNestedMathView(latex);
    return (
      <View style={[styles.wrap, styles.fallbackBox]} testID="math-svg-fallback">
        <ScrollView
          horizontal
          nestedScrollEnabled
          showsHorizontalScrollIndicator
          contentContainerStyle={styles.lineScroll}
        >
          {hasNestedView ? (
            <View style={styles.nestedRow}>
              <MathText latex={latex} textColor={textColor} />
            </View>
          ) : (
            <Text style={styles.line} selectable>
              <MathText latex={latex} textColor={textColor} />
            </Text>
          )}
        </ScrollView>
      </View>
    );
  }

  const width = Math.max(1, result.widthEx * EX_PX);
  const height = Math.max(minHeight, result.heightEx * EX_PX);
  return (
    <View style={styles.wrap}>
      <ScrollView
        horizontal
        nestedScrollEnabled
        showsHorizontalScrollIndicator
        style={{ height }}
        contentContainerStyle={styles.lineScroll}
      >
        <SvgXml xml={xml} width={width} height={height} testID="math-svg" />
      </ScrollView>
    </View>
  );
});

const styles = StyleSheet.create({
  wrap: {
    alignSelf: "stretch",
    width: "100%",
  },
  fallbackBox: {
    paddingVertical: 10,
    paddingHorizontal: Space.xxs,
  },
  lineScroll: {
    flexGrow: 1,
    justifyContent: "center",
    minWidth: "100%",
    paddingHorizontal: Space.xs,
  },
  line: {
    textAlign: "center",
    lineHeight: MATH_TALL_LINE_HEIGHT,
  },
  // Hosts a nested math View (sqrt/frac) as a direct child so iOS doesn't
  // clip it to a Text line box. Centers the run like the `line` Text would.
  nestedRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    flexWrap: "nowrap",
  },
});
