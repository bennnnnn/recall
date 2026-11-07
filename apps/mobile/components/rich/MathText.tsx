import { memo, useMemo, type ReactNode } from "react";
import { ScrollView, Text, useWindowDimensions, View } from "react-native";

import { inlineMathNeedsScroll, layoutMath } from "@/lib/math/layout";
import { fixImplicitExponents } from "@/lib/math/normalizeImplicit";
import { parseSimpleLatex, readableLatexFallback } from "@/lib/math/text";
import { useTheme } from "@/lib/theme";
import { makeStyles } from "@/components/rich/mathText/styles";
import { scaled, type RenderCtx } from "@/components/rich/mathText/context";
import {
  hasStackedMath,
  hasTallMath,
  renderSegments,
} from "@/components/rich/mathText/render";

type Props = {
  latex: string;
  textColor?: string;
  /** Tight line box — for hosts that draw their own rule above the content
   * (the composer radicand slot), where base leading pushes ink off the bar. */
  compact?: boolean;
  /** Used by editable root degrees; layout scales with the actual text size. */
  fontSize?: number;
  /** Markdown's View host can constrain tall runs and scroll their full width.
   * Leave this off in editable math slots and hosts with their own viewport. */
  scrollOverflow?: boolean;
};


/**
 * A formula with raised, dropped or stacked parts, as a View. Its first child is an empty
 * run in the formula's own face, centred as every run of the formula is, so the View's
 * baseline is the formula's: a row that aligns by baseline sets `v_0` and `h_{max}` on
 * the line of the words beside them, not centred on that line's box (where a subscript
 * pulled the formula up and an exponent pushed it down).
 */
function TallMath({
  layout,
  styles,
  fontScale,
  minWidth,
  height,
  children,
}: {
  layout: ReturnType<typeof layoutMath>;
  styles: ReturnType<typeof makeStyles>;
  fontScale: number;
  minWidth: number;
  height: number;
  children: ReactNode;
}) {
  // The measured height already includes the script raise. Padding keeps
  // that room inside the box so translateY lifts the exponent into it
  // instead of painting past the top, where a ScrollView would clip it.
  const padTop = scaled(layout.padTop ?? 0, fontScale);
  const padBottom = scaled(layout.padBottom ?? 0, fontScale);
  // The measured width is a floor, not the box: advances are estimates, and
  // a box narrower than its glyphs let them paint over the space after the
  // formula ("→ 2H₂Oshows"). The glyph runs inside widen it to their ink.
  return (
    <View
      testID="math-text-tall"
      collapsable={false}
      style={[styles.tallRoot, {
        minWidth,
        height,
        ...(padTop > 0 ? { paddingTop: padTop } : null),
        ...(padBottom > 0 ? { paddingBottom: padBottom } : null),
      }]}
    >
      <Text testID="math-baseline" style={styles.base} accessible={false}>
        {"\u200B"}
      </Text>
      {children}
    </View>
  );
}

/** Memoized: a markdown run re-renders on every streamed flush, and its unchanged formulas
 * keep their layout instead of being laid out again. */
export const MathText = memo(function MathText({
  latex,
  textColor,
  compact = false,
  fontSize = 16,
  scrollOverflow = false,
}: Props) {
  const theme = useTheme();
  const color = textColor ?? theme.text;
  const { fontScale, width: windowWidth } = useWindowDimensions();
  const styles = useMemo(
    () => makeStyles(theme, textColor, compact, fontSize, fontScale),
    [theme, textColor, compact, fontSize, fontScale],
  );
  const segments = useMemo(
    () => parseSimpleLatex(fixImplicitExponents(latex.trim())),
    [latex],
  );
  const layout = useMemo(() => layoutMath(segments, fontSize), [segments, fontSize]);
  const tall = useMemo(() => hasTallMath(segments), [segments]);
  const stacked = useMemo(() => hasStackedMath(segments), [segments]);
  const ctx: RenderCtx = { styles, color, fontScale, em: fontSize };

  if (!latex.trim()) return null;

  const contentWidth = scaled(layout.width, fontScale);
  const contentHeight = scaled(layout.height, fontScale);
  const label = readableLatexFallback(latex);
  // A short power stays a View so the exponent can rise, without the
  // horizontal scroller that stacked fractions use even when they fit.
  const scroll = scrollOverflow && (stacked || inlineMathNeedsScroll(contentWidth, windowWidth));
  const runs = renderSegments(segments, layout.children, "m", ctx);

  // Stacked structures are a View root. Text > Text > View is what iOS lays
  // out as 0×0 and paints over the next line.
  if (tall) {
    const content = (
      <TallMath layout={layout} styles={styles} fontScale={fontScale} minWidth={contentWidth} height={contentHeight}>
        {runs}
      </TallMath>
    );
    if (!scroll) return content;
    // The viewport is the paragraph width. The formula keeps its measured
    // width and scrolls; it is not shrunk to fit.
    return (
      <ScrollView
        testID="math-text-scroll"
        horizontal
        nestedScrollEnabled
        directionalLockEnabled
        showsHorizontalScrollIndicator
        bounces={false}
        contentInsetAdjustmentBehavior="never"
        accessible
        accessibilityRole="text"
        accessibilityLabel={label}
        style={[styles.inlineViewport, { height: contentHeight }]}
      >
        {content}
      </ScrollView>
    );
  }

  const lineHeight = Math.max(styles.base.lineHeight ?? 0, layout.height);
  if (scroll) {
    return (
      <ScrollView
        testID="math-text-scroll"
        horizontal
        nestedScrollEnabled
        directionalLockEnabled
        showsHorizontalScrollIndicator
        bounces={false}
        contentInsetAdjustmentBehavior="never"
        accessible
        accessibilityRole="text"
        accessibilityLabel={label}
        style={[styles.inlineViewport, { height: contentHeight }]}
      >
        <Text
          testID="math-text-wide"
          style={[styles.base, { lineHeight, minWidth: contentWidth, flexShrink: 0 }]}
        >
          {runs}
        </Text>
      </ScrollView>
    );
  }

  return (
    <Text style={[styles.base, { lineHeight }]}>
      {runs}
    </Text>
  );
});
