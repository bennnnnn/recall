import { memo, useMemo, type ReactNode } from "react";
import {
  ScrollView,
  Text,
  useWindowDimensions,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";

import { useInsideAccessibleElement } from "@/components/rich/accessibleElement";
import { useMathColumnInset } from "@/components/rich/mathColumn";
import { inlineMathNeedsScroll, layoutMath } from "@/lib/math/layout";
import { fixImplicitExponents } from "@/lib/math/normalizeImplicit";
import { parseSimpleLatex, spokenFormula } from "@/lib/math/text";
import { useTheme } from "@/lib/theme";
import { makeStyles } from "@/components/rich/mathText/styles";
import { scaled, type RenderCtx } from "@/components/rich/mathText/context";
import {
  hasStackedMath,
  hasTallMath,
  renderSegments,
} from "@/components/rich/mathText/render";
import { endsOnItalicLetter, ITALIC_LEAN_EM } from "@/components/rich/mathText/runs";

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
  /** Room after a last italic letter, which the composer draft's own box cut off (`P`
   * drew as `F`). Only that draft asks for it; a reply's maths is drawn without it. */
  lean?: boolean;
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
  height,
  label,
  children,
}: {
  layout: ReturnType<typeof layoutMath>;
  styles: ReturnType<typeof makeStyles>;
  fontScale: number;
  height: number;
  /** The formula read as words, when this box is its one screen-reader element. */
  label?: string;
  children: ReactNode;
}) {
  // The measured height already includes the script raise. Padding keeps
  // that room inside the box so translateY lifts the exponent into it
  // instead of painting past the top, where a ScrollView would clip it.
  const padTop = scaled(layout.padTop ?? 0, fontScale);
  const padBottom = scaled(layout.padBottom ?? 0, fontScale);
  // The box is as wide as what it draws: its glyph runs measure their own ink, and its
  // fractions and roots carry their laid-out widths. The estimated width is neither a cap
  // nor a floor. As a cap the glyphs ran past it over the next word ("→ 2H₂Oshows"); as a
  // floor its overestimate (a 0.33 em space where KaTeX_Main draws 0.25) was empty room
  // after the last glyph, a gap before the mark that follows ("15 m/s ?").
  return (
    <View
      testID="math-text-tall"
      collapsable={false}
      accessible={label !== undefined}
      accessibilityRole={label !== undefined ? "text" : undefined}
      accessibilityLabel={label}
      style={[styles.tallRoot, {
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

/** A formula wider than the paragraph, scrolled sideways inside it; when it reads the
 * formula to a screen reader (``label``), it is the formula's one element. */
function InlineMathScroll({
  label,
  style,
  children,
}: {
  label: string | undefined;
  style: StyleProp<ViewStyle>;
  children: ReactNode;
}) {
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      testID="math-text-scroll"
      horizontal
      nestedScrollEnabled
      directionalLockEnabled
      showsHorizontalScrollIndicator
      bounces={false}
      contentInsetAdjustmentBehavior="never"
      accessible={label !== undefined}
      accessibilityRole={label !== undefined ? "text" : undefined}
      accessibilityLabel={label}
      style={style}
    >
      {children}
    </ScrollView>
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
  lean = false,
}: Props) {
  const theme = useTheme();
  const color = textColor ?? theme.text;
  const { fontScale, width: windowWidth } = useWindowDimensions();
  const inset = useMathColumnInset();
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
  // Under an accessible parent (an answer card, a grouped paragraph) the parent
  // reads the formula; a focusable box here would be a second TalkBack stop.
  const own = !useInsideAccessibleElement();

  if (!latex.trim()) return null;

  const contentWidth = scaled(layout.width, fontScale);
  const contentHeight = scaled(layout.height, fontScale);
  const label = spokenFormula(latex);
  // A short power stays a View so the exponent can rise, without the
  // horizontal scroller that stacked fractions use even when they fit.
  const scroll =
    scrollOverflow && (stacked || inlineMathNeedsScroll(contentWidth, windowWidth - inset));
  // A row of Views leans its last run; one Text leans its own box, below.
  const runs = renderSegments(segments, layout.children, "m", tall && lean ? { ...ctx, leanLast: true } : ctx);
  const last = segments.at(-1);
  const leanPad = lean && last?.type === "text" && endsOnItalicLetter(last.value)
    ? { paddingRight: ITALIC_LEAN_EM * fontSize * fontScale }
    : null;

  // Stacked structures are a View root. Text > Text > View is what iOS lays
  // out as 0×0 and paints over the next line.
  if (tall) {
    // Unscrolled, the box is the formula's one screen-reader element: its
    // pieces (a numerator, a radicand) would otherwise be read apart, or not
    // at all. Scrolled, the ScrollView below carries the label.
    const boxOwns = own && !scroll;
    const content = (
      <TallMath
        layout={layout}
        styles={styles}
        fontScale={fontScale}
        height={contentHeight}
        label={boxOwns ? label : undefined}
      >
        {runs}
      </TallMath>
    );
    if (!scroll) return content;
    // The viewport is the paragraph width. The formula keeps its full
    // width and scrolls; it is not shrunk to fit.
    return (
      <InlineMathScroll label={own ? label : undefined} style={[styles.inlineViewport, { height: contentHeight }]}>
        {content}
      </InlineMathScroll>
    );
  }

  const lineHeight = Math.max(styles.base.lineHeight ?? 0, layout.height);
  if (scroll) {
    return (
      <InlineMathScroll label={own ? label : undefined} style={[styles.inlineViewport, { height: contentHeight }]}>
        <Text
          testID="math-text-wide"
          style={[styles.base, { lineHeight, minWidth: contentWidth, flexShrink: 0 }, leanPad]}
        >
          {runs}
        </Text>
      </InlineMathScroll>
    );
  }

  return (
    <Text style={[styles.base, { lineHeight }, leanPad]}>
      {runs}
    </Text>
  );
});
