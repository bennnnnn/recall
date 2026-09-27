import { useMemo, type ReactNode } from "react";
import { Platform, ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import Svg, { Path } from "react-native-svg";

import { MATH_FONT, MATH_VARIABLE_FONT } from "@/lib/fonts";
import { fixImplicitExponents } from "@/lib/math/normalizeImplicit";
import {
  parseSimpleLatex,
  readableLatexFallback,
  type MathSegment,
} from "@/lib/math/text";
import { toSubscript, toSuperscript } from "@/lib/unicodeSupSub";
import { Theme, useTheme } from "@/lib/theme";
import { Space } from "@/lib/space";

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

type Styles = ReturnType<typeof makeStyles>;

const FRAC_CHAR_PX = 9;
/** Fraction text is 14px when the math size is 16. Widths below are in that
 * unscaled space and get multiplied by layoutScale. */
const FRAC_EM = 14;
const BASE_EM = 16;
/** A real vinculum only overhangs its widest glyph slightly. The old 14px
 * padding added seven pixels per side, making 1/2 look like a blank rule. */
const FRAC_PAD_PX = 4;
const FRAC_STACK_HEIGHT = 44;
const FRAC_LINE_HEIGHT = 18;
const FRACTIONAL_SCRIPT_HEIGHT = 30;
/** Math glyph layout needs a numeric line box; unlike prose Type roles, this
 * scales with the requested math size and React Native's system font scale. */
const MATH_BODY_LINE_HEIGHT = 25;
/** Simple radicands use this tight line box. The radical path adds only its
 * small top inset; nested fractions contribute their full measured height. */
const SQRT_LINE_HEIGHT = 20;
const RADICAL_MIN_LEAD_PX = 13;
const RADICAL_BODY_TOP_PX = 2;
const RADICAL_STROKE_PX = 1.35;

/** SpaceMono has no (or a broken) U+2260 — fallback looks like slashed ≡. */
const MATH_OPERATOR_CHARS = new Set(
  Array.from("≠≤≥≈∞±∓×÷∈⊂⊆⊃≡∝∼∀∃∅∠⊥∥⟨⟩∘∨∧∖"),
);

/** Named operators are words, not products of variables, so they stay
 * upright in the same way KaTeX renders `sin`, `log`, and `mod`. */
const UPRIGHT_MATH_WORDS = new Set([
  "arccos", "arcsin", "arctan", "cos", "cosh", "cot", "csc", "det",
  "exp", "gcd", "if", "lim", "ln", "log", "max", "min", "mod",
  "otherwise", "rank", "sec", "sin", "sinh", "tan", "tanh", "where",
]);

const MATH_LETTER_RUN = /[A-Za-z\u0370-\u03ff]+/g;

function isUprightWord(value: string): boolean {
  return UPRIGHT_MATH_WORDS.has(value.toLowerCase());
}

function renderNonVariableRun(
  value: string,
  key: string,
  glyphStyle: object,
): ReactNode[] {
  return Array.from(value).map((ch, i) =>
    MATH_OPERATOR_CHARS.has(ch) ? (
      <Text key={`${key}-g${i}`} style={glyphStyle}>
        {ch}
      </Text>
    ) : (
      ch
    ),
  );
}

function renderMathRun(
  value: string,
  key: string,
  textStyle: object,
  glyphStyle: object,
  variableStyle: object,
): ReactNode {
  const children: ReactNode[] = [];
  let cursor = 0;
  let variableIndex = 0;
  for (const match of value.matchAll(MATH_LETTER_RUN)) {
    const start = match.index ?? 0;
    if (start > cursor) {
      children.push(
        ...renderNonVariableRun(
          value.slice(cursor, start),
          `${key}-t${cursor}`,
          glyphStyle,
        ),
      );
    }
    const word = match[0];
    children.push(
      isUprightWord(word) ? word : (
        <Text
          key={`${key}-v${variableIndex}`}
          testID="math-variable"
          style={[textStyle, variableStyle]}
        >
          {word}
        </Text>
      ),
    );
    variableIndex += 1;
    cursor = start + word.length;
  }
  if (cursor < value.length) {
    children.push(
      ...renderNonVariableRun(value.slice(cursor), `${key}-t${cursor}`, glyphStyle),
    );
  }
  return (
    <Text key={key} style={textStyle}>
      {children}
    </Text>
  );
}

function visualLength(s: string): number {
  let n = 0;
  for (const ch of s) {
    if (!isCombiningMark(ch)) n += 1;
  }
  return n;
}

function isCombiningMark(ch: string): boolean {
  const c = ch.charCodeAt(0);
  return c >= 0x0300 && c <= 0x036f;
}

/** Computer Modern is proportional. m/w are about one em, so the old
 * one-width estimate (SpaceMono) clips a long numerator and its scroll. */
function isWideFormulaGlyph(ch: string): boolean {
  return ch === "m" || ch === "w" || ch === "M" || ch === "W" || ch === "%" || ch === "@";
}

function advancePx(text: string, em: number): number {
  let width = 0;
  let counted = false;
  for (const ch of text) {
    if (isCombiningMark(ch)) continue;
    counted = true;
    // Narrow glyphs keep the old monospace advance so digit fractions stay put.
    width += isWideFormulaGlyph(ch) ? em : FRAC_CHAR_PX;
  }
  return counted ? width : FRAC_CHAR_PX;
}

function estimateSegmentsSize(segments: MathSegment[], inFrac = false): { width: number; height: number } {
  let width = 0;
  let height = inFrac ? FRAC_LINE_HEIGHT : SQRT_LINE_HEIGHT;
  for (const seg of segments) {
    if (seg.type === "frac") {
      const box = fracStackSize(seg.num, seg.den);
      width += box.width + 6;
      height = Math.max(height, box.height);
    } else if (seg.type === "sqrt") {
      const box = radicalBoxSize(seg.body, inFrac, seg.degree);
      width += box.width;
      height = Math.max(height, box.height);
    } else if (seg.type === "cancel") {
      const inner = estimateSegmentsSize(seg.body, inFrac);
      width += inner.width;
      height = Math.max(height, inner.height);
    } else {
      width += advancePx(seg.value, inFrac ? FRAC_EM : BASE_EM);
      if (isFractionalScript(seg)) height = Math.max(height, FRACTIONAL_SCRIPT_HEIGHT);
    }
  }
  return { width, height };
}

function radicalBoxSize(
  segments: MathSegment[],
  inFrac: boolean,
  degree?: string,
): { width: number; height: number; lead: number; body: { width: number; height: number } } {
  const body = estimateSegmentsSize(segments, inFrac);
  const indexLead = degree ? visualLength(degree) * 7 + 5 : 0;
  const lead = Math.max(RADICAL_MIN_LEAD_PX, indexLead);
  return {
    width: lead + body.width,
    height: Math.max(SQRT_LINE_HEIGHT, body.height + RADICAL_BODY_TOP_PX),
    lead,
    body,
  };
}

function fracStackSize(num: MathSegment[], den: MathSegment[]): { width: number; height: number } {
  // The vinculum already groups each complete side. Only parentheses in the
  // source belong here; invented ones also inflate the inline attachment.
  const numerator = estimateSegmentsSize(num, true);
  const denominator = estimateSegmentsSize(den, true);
  return {
    width: Math.max(numerator.width, denominator.width, FRAC_CHAR_PX) + FRAC_PAD_PX,
    // Nested fractions must contribute their full height to the outer stack.
    height: Math.max(FRAC_STACK_HEIGHT, numerator.height + denominator.height + 6),
  };
}

function isFractionalScript(seg: MathSegment): boolean {
  return seg.type === "sup" && seg.value.includes("/");
}

function estimateMathTextSize(segments: MathSegment[]): { width: number; height: number } {
  const { width, height } = estimateSegmentsSize(segments);
  return { width: Math.max(width, 24), height };
}

function hasTallMath(segments: MathSegment[]): boolean {
  for (const seg of segments) {
    if (seg.type === "frac" || seg.type === "sqrt" || seg.type === "cancel" || isFractionalScript(seg)) {
      return true;
    }
  }
  return false;
}

type RenderCtx = {
  styles: Styles;
  color: string;
  /** Fraction-sized run — numerator/denominator content stays small. */
  inFrac?: boolean;
  /** Overrides the run style for the whole subtree (radicand line box). */
  textStyle?: object;
  layoutScale: number;
};

function runStyle(ctx: RenderCtx): object {
  if (ctx.textStyle) return ctx.textStyle;
  return ctx.inFrac ? ctx.styles.fracPart : ctx.styles.base;
}

function renderFracSide(
  segments: MathSegment[],
  keyPrefix: string,
  ctx: RenderCtx,
): ReactNode {
  const { styles } = ctx;
  // Nested fraction OR a radical: keep real Views. Flattening `\sqrt{b^2 - 4ac}`
  // to combining overlines made the minus look like `=` and inflated the bar.
  if (hasTallMath(segments)) {
    return (
      <View style={styles.fracSideRow}>
        {renderSegments(segments, keyPrefix, { ...ctx, inFrac: true })}
      </View>
    );
  }
  return (
    <Text style={styles.fracPart}>
      {renderSegments(segments, keyPrefix, { ...ctx, inFrac: true })}
    </Text>
  );
}

/**
 * Radicand keeps the surrounding text size. Reusing the fraction-sized side
 * renderer made `\sqrt{8}` read as a subscript, and its plain-text flattening
 * leaked scripts as literal `8^3`. Nested stacks still take the View path (a
 * View cannot live in that Text).
 */
function renderRadicand(
  segments: MathSegment[],
  keyPrefix: string,
  ctx: RenderCtx,
): ReactNode {
  const { styles } = ctx;
  const nested = hasTallMath(segments);
  if (nested) {
    return <View style={styles.fracSideRow}>{renderSegments(segments, keyPrefix, ctx)}</View>;
  }
  const bodyStyle = ctx.inFrac ? styles.fracPart : styles.sqrtBody;
  return (
    <Text style={bodyStyle}>
      {renderSegments(segments, keyPrefix, {
        ...ctx,
        inFrac: ctx.inFrac,
        textStyle: bodyStyle,
      })}
    </Text>
  );
}

function renderSegments(
  segments: MathSegment[],
  keyPrefix: string,
  ctx: RenderCtx,
): ReactNode[] {
  const { styles, inFrac } = ctx;
  return segments.map((seg, i) => {
    const key = `${keyPrefix}-${i}`;
    if (seg.type === "sup") {
      if (isFractionalScript(seg)) {
        // Unicode ¹⁄⁶ uses miniature glyphs even at body size. A genuinely
        // raised 14px run keeps both digits and the fraction slash readable.
        return (
          <View key={key} style={styles.fractionalSup} testID="math-fractional-sup">
            <Text style={styles.scriptText}>{seg.value}</Text>
          </View>
        );
      }
      const uni = toSuperscript(seg.value);
      const node = uni ?? seg.value;
      return (
        <Text key={key} style={uni ? runStyle(ctx) : styles.sup}>
          {node}
        </Text>
      );
    }
    if (seg.type === "sub") {
      const uni = toSubscript(seg.value);
      const node = uni ?? seg.value;
      return (
        <Text key={key} style={uni ? runStyle(ctx) : styles.sub}>
          {node}
        </Text>
      );
    }
    if (seg.type === "frac") {
      // True stacked fraction with a vinculum. Sized View — the paragraph
      // Text treats it as a character. Do not wrap this in another Text.
      const box = fracStackSize(seg.num, seg.den);
      return (
        <View
          key={key}
          style={[styles.fracStack, { width: box.width * ctx.layoutScale, height: box.height * ctx.layoutScale }]}
          testID="math-frac"
          collapsable={false}
        >
          {renderFracSide(seg.num, `${key}-n`, ctx)}
          <View style={styles.vinculum} testID="math-vinculum" />
          {renderFracSide(seg.den, `${key}-d`, ctx)}
        </View>
      );
    }
    if (seg.type === "sqrt") {
      const box = radicalBoxSize(seg.body, Boolean(inFrac), seg.degree);
      const width = box.width * ctx.layoutScale;
      const height = box.height * ctx.layoutScale;
      const top = 1;
      const hook = Math.max(top + 7, box.height * 0.56);
      const bottom = box.height - 1;
      const rise = box.lead - 1;
      return (
        <View
          key={key}
          style={[
            styles.sqrtRow,
            !seg.degree && styles.sqrtAfterCoeff,
            { width, height },
          ]}
          testID="math-sqrt"
          collapsable={false}
        >
          <Svg
            testID="math-radical-glyph"
            width={width}
            height={height}
            viewBox={`0 0 ${box.width} ${box.height}`}
            style={styles.radicalGlyph}
            pointerEvents="none"
            accessible={false}
          >
            <Path
              d={`M 0 ${hook} L 3 ${hook} L 5.5 ${bottom} L ${rise} ${top} L ${box.width} ${top}`}
              fill="none"
              stroke={ctx.color}
              strokeWidth={RADICAL_STROKE_PX}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </Svg>
          {seg.degree ? (
            <Text style={styles.sqrtIndex}>{seg.degree}</Text>
          ) : null}
          <View
            style={[
              styles.sqrtRadicand,
              {
                marginLeft: box.lead * ctx.layoutScale,
                marginTop: RADICAL_BODY_TOP_PX * ctx.layoutScale,
                width: box.body.width * ctx.layoutScale,
                height: box.body.height * ctx.layoutScale,
              },
            ]}
            testID="math-sqrt-radicand"
          >
            {renderRadicand(seg.body, `${key}-b`, ctx)}
          </View>
        </View>
      );
    }
    if (seg.type === "cancel") {
      return (
        <View key={key} testID="math-cancel" style={styles.cancelWrap} collapsable={false}>
          {renderSegments(seg.body, `${key}-c`, ctx)}
          <View style={styles.cancelSlashHit} pointerEvents="none" accessible={false}>
            <View testID="math-cancel-slash" style={styles.cancelSlash} />
          </View>
        </View>
      );
    }
    if (seg.type === "upright") {
      return (
        <Text key={key} style={runStyle(ctx)} testID="math-upright-run">
          {renderNonVariableRun(seg.value, `${key}-u`, styles.glyph)}
        </Text>
      );
    }
    return renderMathRun(
      seg.value,
      key,
      runStyle(ctx),
      styles.glyph,
      styles.variable,
    );
  });
}

/** Native math: simple runs stay Text; stacked or raised structures own their bounds. */
export function MathText({ latex, textColor, compact = false, fontSize = 16, scrollOverflow = false }: Props) {
  const theme = useTheme();
  const color = textColor ?? theme.text;
  const { fontScale } = useWindowDimensions();
  const layoutScale = (fontSize / 16) * fontScale;
  const styles = useMemo(
    () => makeStyles(theme, textColor, compact, fontSize, fontScale),
    [theme, textColor, compact, fontSize, fontScale],
  );
  const segments = useMemo(
    () => parseSimpleLatex(fixImplicitExponents(latex.trim())),
    [latex],
  );
  const tall = useMemo(() => hasTallMath(segments), [segments]);

  if (!latex.trim()) return null;

  // Stacked frac is a View. It must be the MathText root (not wrapped in
  // Text) so the paragraph Text can treat it as a sized character. Text >
  // Text > View is what iOS lays out as 0×0 and paints over the next line.
  if (tall) {
    const size = estimateMathTextSize(segments);
    const content = (
      <View
        testID="math-text-tall"
        collapsable={false}
        style={[styles.tallRoot, {
          ...(scrollOverflow ? { minWidth: size.width * layoutScale } : { width: size.width * layoutScale }),
          height: size.height * layoutScale,
        }]}
      >
        {renderSegments(segments, "m", { styles, color, layoutScale })}
      </View>
    );
    if (!scrollOverflow) return content;
    // Keep short fractions at their intrinsic size. A longer run is limited
    // by its actual paragraph/list width, while its inner row never shrinks.
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
        accessibilityLabel={readableLatexFallback(latex)}
        style={[
          styles.inlineViewport,
          { width: size.width * layoutScale, height: size.height * layoutScale },
        ]}
      >
        {content}
      </ScrollView>
    );
  }

  return (
    <Text style={styles.base}>
      {renderSegments(segments, "m", { styles, color, layoutScale })}
    </Text>
  );
}

const makeStyles = (theme: Theme, textColor?: string, compact = false, fontSize = 16, fontScale = 1) => {
  const color = textColor ?? theme.text;
  const scale = fontSize / 16;
  const layoutScale = scale * fontScale;
  return StyleSheet.create({
    base: {
      fontFamily: MATH_FONT,
      fontSize,
      // Match body rhythm. 28 made nested `$m$` / `$y=mx+b$` Text
      // wrap onto its own line inside list items ("Slope (" / "m" / "): 3").
      lineHeight: (compact ? SQRT_LINE_HEIGHT : MATH_BODY_LINE_HEIGHT) * scale,
      color,
    },
    glyph: {
      // KaTeX Main does not carry every Unicode relation symbol.
      fontFamily: Platform.select({
        ios: "Helvetica Neue",
        android: "sans-serif",
        default: undefined,
      }),
    },
    variable: {
      fontFamily: MATH_VARIABLE_FONT,
      color,
    },
    inlineViewport: {
      maxWidth: "100%",
      flexGrow: 0,
      flexShrink: 1,
    },
    tallRoot: {
      flexDirection: "row",
      alignItems: "center",
      flexShrink: 0,
      overflow: "visible",
    },
    sup: {
      fontFamily: MATH_FONT,
      fontSize: 11,
      lineHeight: 14,
      color,
    },
    sub: {
      fontFamily: MATH_FONT,
      fontSize: 11,
      lineHeight: 14,
      color,
    },
    fractionalSup: {
      paddingBottom: Space.sm * layoutScale,
    },
    scriptText: {
      fontFamily: MATH_FONT,
      fontSize: 14 * scale,
      lineHeight: FRAC_LINE_HEIGHT * scale,
      color,
    },
    fracStack: {
      alignItems: "center",
      alignSelf: "flex-start",
      justifyContent: "center",
      marginHorizontal: 3 * layoutScale,
      overflow: "visible",
      flexShrink: 0,
    },
    fracSideRow: {
      flexDirection: "row",
      alignItems: "center",
    },
    fracPart: {
      fontFamily: MATH_FONT,
      fontSize: 14 * scale,
      lineHeight: FRAC_LINE_HEIGHT * scale,
      color,
      textAlign: "center",
    },
    // One SVG path draws hook, rising stroke, and bar continuously. Its height
    // is derived from the radicand, so a stacked denominator stays inside it.
    sqrtRow: {
      flexDirection: "row",
      alignItems: "flex-start",
      marginHorizontal: 2 * layoutScale,
      overflow: "visible",
    },
    sqrtAfterCoeff: {
      marginLeft: 6 * layoutScale,
    },
    sqrtIndex: {
      position: "absolute",
      left: 0,
      top: 0,
      fontFamily: MATH_FONT,
      fontSize: 12 * scale,
      lineHeight: 14 * scale,
      color,
      transform: [{ translateY: -4 * layoutScale }],
    },
    sqrtBody: {
      fontFamily: MATH_FONT,
      fontSize,
      lineHeight: SQRT_LINE_HEIGHT * scale,
      color,
    },
    sqrtRadicand: {
      flexDirection: "row",
      alignItems: "flex-start",
      overflow: "visible",
    },
    radicalGlyph: {
      position: "absolute",
      left: 0,
      top: 0,
    },
    vinculum: {
      alignSelf: "stretch",
      height: StyleSheet.hairlineWidth * 2,
      marginVertical: 2 * layoutScale,
      backgroundColor: color,
    },
    cancelWrap: {
      alignItems: "center",
      justifyContent: "center",
    },
    cancelSlashHit: {
      ...StyleSheet.absoluteFill,
      alignItems: "center",
      justifyContent: "center",
    },
    cancelSlash: {
      width: "140%",
      height: 1.5 * layoutScale,
      backgroundColor: theme.danger,
      transform: [{ rotate: "-32deg" }],
    },
  });
};
