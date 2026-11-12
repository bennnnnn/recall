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
  spokenFormula,
} from "@/lib/math/text";
import { fittedIndent } from "@/lib/math/layout";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";

/** MathJax metrics: the SVG viewBox runs 1000 units per em and 1ex ≈ 0.442em (measured). */
const EX_PER_EM = 0.442;

type Props = {
  latex: string;
  textColor: string;
  minHeight?: number;
  /**
   * The type size (em) the formula is set at; the reply's text size by default, as TeX sets
   * a display at the size of its paragraph: the 20px em the retired KaTeX WebView used drew
   * every display formula a size larger than the inline maths and the words around it. The
   * drawing is then scaled by the reader's text size (Larger Text), as inline maths
   * (`MathText`) and body copy scale: uncapped, and a formula wider than the line scrolls.
   */
  em?: number;
  /**
   * `start` sets the formula at the left edge of the text column it sits in, with the
   * lines around it (a reply); `center` centres it in its box (the answer card).
   */
  align?: "start" | "center";
  /**
   * The working column's indent (a reply's own display maths): kept while the formula fits
   * after it, given up as it grows, so a long formula reaches the right edge only when the
   * whole line cannot hold it (``fittedIndent``).
   */
  indent?: number;
};

type FallbackProps = Required<Omit<Props, "minHeight" | "indent">> & { label: string | undefined };

/** What MathJax could not convert: the same formula in readable native maths. */
function FallbackMath({ latex, textColor, em, align, label }: FallbackProps) {
  const justify = align === "start" ? styles.alignStart : null;
  const own = label !== undefined;
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
          keyboardShouldPersistTaps="handled"
          horizontal
          nestedScrollEnabled
          showsHorizontalScrollIndicator
          contentContainerStyle={[styles.lineScroll, justify]}
        >
          {latexHasNestedMathView(latex) ? (
            <View style={[styles.nestedRow, justify]}>
              <MathText latex={latex} textColor={textColor} fontSize={em} />
            </View>
          ) : (
            <Text style={[styles.line, align === "start" && styles.lineStart]} selectable>
              <MathText latex={latex} textColor={textColor} fontSize={em} />
            </Text>
          )}
        </ScrollView>
      </AccessibleElementChildren>
    </View>
  );
}

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
  em = Type.reading.fontSize,
  align = "center",
  indent = 0,
}: Props) {
  const { fontScale, width: windowWidth } = useWindowDimensions();
  const exPx = em * EX_PER_EM * fontScale;
  const justify = align === "start" ? styles.alignStart : null;
  // VoiceOver reads the formula as words: an SVG has no text of its own. Under
  // an accessible parent (an answer card) the parent reads it instead.
  const own = !useInsideAccessibleElement();
  const label = useMemo(() => (own ? spokenFormula(latex) : undefined), [own, latex]);
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

  const indented = indent > 0 ? { paddingLeft: indent } : null;
  if (result === undefined) {
    return <View style={[styles.wrap, indented, { minHeight }]} testID="math-svg-loading" />;
  }

  if (result === null || ast == null) {
    return (
      <View style={indented}>
        <FallbackMath latex={latex} textColor={textColor} em={em} align={align} label={label} />
      </View>
    );
  }

  // Intrinsic size. minHeight is only the loading slot: stretching a short
  // MathJax SVG up to 48px turns `gt` and a limit into a smashed bar.
  const width = Math.max(1, result.widthEx * exPx);
  const height = Math.max(1, result.heightEx * exPx);
  return (
    <View
      style={[styles.wrap, indent > 0 && { paddingLeft: fittedIndent(indent, width, windowWidth) }]}
      testID="math-svg-view"
      accessible={own}
      accessibilityRole={own ? "text" : undefined}
      accessibilityLabel={label}
    >
      <ScrollView
        keyboardShouldPersistTaps="handled"
        horizontal
        nestedScrollEnabled
        showsHorizontalScrollIndicator
        testID="math-svg-scroll"
        style={{ height }}
        contentContainerStyle={[styles.lineScroll, justify]}
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
  lineStart: { textAlign: "left" },
  // At the start the formula's first glyph lines up with the text column's edge.
  alignStart: { justifyContent: "flex-start", paddingLeft: 0 },
  // Hosts a nested math View (sqrt/frac) as a direct child so iOS doesn't
  // clip it to a Text line box. Centers the run like the `line` Text would.
  nestedRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    flexWrap: "nowrap",
  },
});
