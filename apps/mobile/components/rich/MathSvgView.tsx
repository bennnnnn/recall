import React, { useEffect, useMemo, useState } from "react";
import { ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { parse, SvgAst, type JsxAST } from "react-native-svg";

import {
  AccessibleElementChildren,
  useInsideAccessibleElement,
} from "@/components/rich/accessibleElement";
import { MathText } from "@/components/rich/MathText";
import {
  latexToSvgMath,
  peekSvgMath,
  svgMathDrawing,
  type SvgMathResult,
} from "@/lib/math/svgMath";
import {
  latexHasNestedMathView,
  MATH_TALL_LINE_HEIGHT,
  readableLatexFallback,
} from "@/lib/math/text";
import { Space } from "@/lib/space";

/**
 * MathJax metrics: the SVG viewBox runs 1000 units per em and 1ex ≈ 0.442em
 * (measured from MathJax output). Render display math at the same 20px em the
 * retired KaTeX WebView used, times the reader's text size (Larger Text), as
 * inline maths (`MathText`) and body copy scale: uncapped, and a formula
 * wider than the line scrolls sideways.
 */
export const MATH_SVG_EX_PX = 20 * 0.442;

type Props = {
  latex: string;
  textColor: string;
  minHeight?: number;
};

/** A conversion and the latex it belongs to (`undefined` while it runs). */
type Loaded = { latex: string; result: SvgMathResult | null | undefined };

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
  const { fontScale } = useWindowDimensions();
  // VoiceOver reads the formula as words: an SVG has no text of its own. Under
  // an accessible parent (an answer card) the parent reads it instead.
  const own = !useInsideAccessibleElement();
  const label = useMemo(() => (own ? readableLatexFallback(latex) : undefined), [own, latex]);
  // The conversion is held with the latex it was made from. A view whose
  // latex changes (a streaming answer growing, a reused row) never draws the
  // previous formula's result, not even for one frame: until its own result
  // arrives it shows the cached one for the new latex, or the loading slot.
  const [loaded, setLoaded] = useState<Loaded>(() => ({
    latex,
    result: peekSvgMath(latex, true),
  }));
  const result = loaded.latex === latex ? loaded.result : peekSvgMath(latex, true);

  useEffect(() => {
    const keep = (next: SvgMathResult | null | undefined) =>
      setLoaded((previous) =>
        previous.latex === latex && previous.result === next ? previous : { latex, result: next },
      );
    const peeked = peekSvgMath(latex, true);
    if (peeked !== undefined) {
      keep(peeked);
      return;
    }
    let live = true;
    keep(undefined);
    void latexToSvgMath(latex, true).then((next) => {
      if (live) keep(next);
    });
    return () => {
      live = false;
    };
  }, [latex]);

  // react-native-svg does not resolve currentColor — substitute the theme
  // color. The parsed tree is kept with the conversion, per color: drawing
  // the same formula again (a reused row, a re-cut streaming piece) parses
  // nothing.
  const ast = useMemo((): JsxAST | null => {
    if (!result) return null;
    try {
      return svgMathDrawing(result, textColor, () =>
        parse(result.svg.split("currentColor").join(textColor)),
      );
    } catch {
      return null;
    }
  }, [result, textColor]);

  if (result === undefined) {
    return <View style={[styles.wrap, { minHeight }]} testID="math-svg-loading" />;
  }

  if (result === null || ast == null) {
    const hasNestedView = latexHasNestedMathView(latex);
    return (
      <View
        style={[styles.wrap, styles.fallbackBox]}
        testID="math-svg-fallback"
        accessible={own}
        accessibilityRole={own ? "text" : undefined}
        accessibilityLabel={label}
      >
        <AccessibleElementChildren>
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
        </AccessibleElementChildren>
      </View>
    );
  }

  // Intrinsic size. minHeight is only the loading slot: stretching a short
  // MathJax SVG up to 48px turns `gt` and a limit into a smashed bar.
  const exPx = MATH_SVG_EX_PX * fontScale;
  const width = Math.max(1, result.widthEx * exPx);
  const height = Math.max(1, result.heightEx * exPx);
  return (
    <View
      style={styles.wrap}
      testID="math-svg-view"
      accessible={own}
      accessibilityRole={own ? "text" : undefined}
      accessibilityLabel={label}
    >
      <ScrollView
        horizontal
        nestedScrollEnabled
        showsHorizontalScrollIndicator
        style={{ height }}
        contentContainerStyle={styles.lineScroll}
      >
        <SvgAst
          ast={ast}
          override={{ width, height, preserveAspectRatio: "xMidYMid meet", testID: "math-svg" }}
        />
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
    paddingVertical: Space.sm,
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
