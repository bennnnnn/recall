import { useMemo, type ReactNode } from "react";
import { Platform, StyleSheet, Text, useWindowDimensions, View } from "react-native";

import { CODE_FONT } from "@/lib/fonts";
import { fixImplicitExponents } from "@/lib/normalizeImplicitMath";
import {
  parseSimpleLatex,
  segmentsToPlain,
  type MathSegment,
} from "@/lib/mathText";
import { toSubscript, toSuperscript } from "@/lib/unicodeSupSub";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  latex: string;
  textColor?: string;
  /** Tight line box — for hosts that draw their own rule above the content
   * (the composer radicand slot), where base leading pushes ink off the bar. */
  compact?: boolean;
  /** Used by editable root degrees; layout scales with the actual text size. */
  fontSize?: number;
};

type Styles = ReturnType<typeof makeStyles>;

/** A single atomic token ("11", "-4", "2a") needs no disambiguating
 * parens in a stacked numerator/denominator; multi-term sides get parens. */
function isAtomicToken(plain: string): boolean {
  return /^[±+\-]?[a-zA-Z0-9]+$/.test(plain);
}

const FRAC_CHAR_PX = 9;
const FRAC_PAD_PX = 14;
const FRAC_STACK_HEIGHT = 44;
const FRAC_LINE_HEIGHT = 18;
const FRACTIONAL_SCRIPT_HEIGHT = 30;
/** Radical sign and radicand share this tight line box so the vinculum (drawn
 * as the radicand's top border) lands on the √ hook. With the base 28px line
 * box the bar floats in the leading, well above both the hook and the digits. */
const SQRT_LINE_HEIGHT = 20;

/** SpaceMono has no (or a broken) U+2260 — fallback looks like slashed ≡. */
const MATH_OPERATOR_CHARS = new Set(
  Array.from("≠≤≥≈∞±∓×÷∈⊂⊆⊃≡∝∼∀∃∅∠⊥∥⟨⟩∘∨∧∖"),
);

function renderMathRun(
  value: string,
  key: string,
  textStyle: object,
  glyphStyle: object,
): ReactNode {
  const chars = Array.from(value);
  if (!chars.some((ch) => MATH_OPERATOR_CHARS.has(ch))) {
    return (
      <Text key={key} style={textStyle}>
        {value}
      </Text>
    );
  }
  return (
    <Text key={key} style={textStyle}>
      {chars.map((ch, i) =>
        MATH_OPERATOR_CHARS.has(ch) ? (
          <Text key={`${key}-g${i}`} style={glyphStyle}>
            {ch}
          </Text>
        ) : (
          ch
        ),
      )}
    </Text>
  );
}

function visualLength(s: string): number {
  let n = 0;
  for (const ch of s) {
    const c = ch.charCodeAt(0);
    // Combining marks (√ overlines, accents) must not inflate the frac box.
    if (c >= 0x0300 && c <= 0x036f) continue;
    n += 1;
  }
  return n;
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
      const body = estimateSegmentsSize(seg.body, inFrac);
      width += 14 + (seg.degree ? visualLength(seg.degree) * 8 + 2 : 4) + body.width;
      height = Math.max(height, body.height + (seg.degree ? 6 : 2));
    } else {
      width += Math.max(visualLength(seg.value), 1) * FRAC_CHAR_PX;
      if (isFractionalScript(seg)) height = Math.max(height, FRACTIONAL_SCRIPT_HEIGHT);
    }
  }
  return { width, height };
}

function fracStackSize(num: MathSegment[], den: MathSegment[]): { width: number; height: number } {
  const sideSize = (side: MathSegment[]) => {
    const plain = segmentsToPlain(side).replace(/[\u0300-\u036f]/g, "");
    const size = estimateSegmentsSize(side, true);
    return { ...size, width: size.width + (isAtomicToken(plain) ? 0 : 2 * FRAC_CHAR_PX) };
  };
  const numerator = sideSize(num);
  const denominator = sideSize(den);
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
    if (seg.type === "frac" || seg.type === "sqrt" || isFractionalScript(seg)) return true;
  }
  return false;
}

type RenderCtx = {
  styles: Styles;
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
  paren: boolean,
): ReactNode {
  const { styles } = ctx;
  // Nested fraction OR a radical: keep real Views. Flattening `\sqrt{b^2 - 4ac}`
  // to combining overlines made the minus look like `=` and inflated the bar.
  if (hasTallMath(segments)) {
    return (
      <View style={styles.fracSideRow}>
        {paren ? <Text style={styles.fracPart}>(</Text> : null}
        {renderSegments(segments, keyPrefix, { ...ctx, inFrac: true })}
        {paren ? <Text style={styles.fracPart}>)</Text> : null}
      </View>
    );
  }
  return (
    <Text style={styles.fracPart}>
      {paren ? "(" : null}
      {renderSegments(segments, keyPrefix, { ...ctx, inFrac: true })}
      {paren ? ")" : null}
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
      const numPlain = segmentsToPlain(seg.num).replace(/[\u0300-\u036f]/g, "");
      const denPlain = segmentsToPlain(seg.den).replace(/[\u0300-\u036f]/g, "");
      const box = fracStackSize(seg.num, seg.den);
      return (
        <View
          key={key}
          style={[styles.fracStack, { width: box.width * ctx.layoutScale, height: box.height * ctx.layoutScale }]}
          testID="math-frac"
          collapsable={false}
        >
          {renderFracSide(seg.num, `${key}-n`, ctx, !isAtomicToken(numPlain))}
          <View style={styles.vinculum} testID="math-vinculum" />
          {renderFracSide(seg.den, `${key}-d`, ctx, !isAtomicToken(denPlain))}
        </View>
      );
    }
    if (seg.type === "sqrt") {
      return (
        <View
          key={key}
          style={[styles.sqrtRow, !seg.degree && styles.sqrtAfterCoeff]}
          testID="math-sqrt"
        >
          {seg.degree ? (
            <Text style={styles.sqrtIndex}>{seg.degree}</Text>
          ) : null}
          <Text style={inFrac ? styles.fracPart : styles.sqrtSign}>√</Text>
          <View style={styles.sqrtRadicand} testID="math-sqrt-radicand">
            {renderRadicand(seg.body, `${key}-b`, ctx)}
          </View>
        </View>
      );
    }
    return renderMathRun(seg.value, key, runStyle(ctx), styles.glyph);
  });
}

/** Native math: simple runs stay Text; stacked or raised structures own their bounds. */
export function MathText({ latex, textColor, compact = false, fontSize = 16 }: Props) {
  const theme = useTheme();
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
    return (
      <View
        testID="math-text-tall"
        collapsable={false}
        style={[styles.tallRoot, { width: size.width * layoutScale, height: size.height * layoutScale }]}
      >
        {renderSegments(segments, "m", { styles, layoutScale })}
      </View>
    );
  }

  return (
    <Text style={styles.base}>
      {renderSegments(segments, "m", { styles, layoutScale })}
    </Text>
  );
}

const makeStyles = (theme: Theme, textColor?: string, compact = false, fontSize = 16, fontScale = 1) => {
  const color = textColor ?? theme.text;
  const scale = fontSize / 16;
  const layoutScale = scale * fontScale;
  return StyleSheet.create({
    base: {
      fontSize,
      // Match body lineHeight (22). 28 made nested `$m$` / `$y=mx+b$` Text
      // wrap onto its own line inside list items ("Slope (" / "m" / "): 3").
      lineHeight: (compact ? SQRT_LINE_HEIGHT : Type.body.lineHeight) * scale,
      color,
    },
    glyph: {
      // Nested Text inherits SpaceMono unless we name a UI face that has ≠.
      fontFamily: Platform.select({
        ios: "Helvetica Neue",
        android: "sans-serif",
        default: undefined,
      }),
    },
    tallRoot: {
      flexDirection: "row",
      alignItems: "center",
      flexShrink: 0,
      overflow: "visible",
    },
    sup: {
      fontSize: 11,
      lineHeight: 14,
      color,
    },
    sub: {
      fontSize: 11,
      lineHeight: 14,
      color,
    },
    fractionalSup: {
      paddingBottom: 12 * layoutScale,
    },
    scriptText: {
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
      fontFamily: CODE_FONT,
      fontSize: 14 * scale,
      lineHeight: FRAC_LINE_HEIGHT * scale,
      color,
      textAlign: "center",
    },
    // Tops share an edge: sign and radicand have the same line box, so the
    // hook meets the bar. `flex-end` bottom-aligned a shorter radicand box and
    // dropped it into subscript position.
    sqrtRow: {
      flexDirection: "row",
      alignItems: "flex-start",
      marginHorizontal: 2 * layoutScale,
    },
    sqrtAfterCoeff: {
      marginLeft: 6 * layoutScale,
    },
    sqrtIndex: {
      fontFamily: CODE_FONT,
      fontSize: 12 * scale,
      lineHeight: 14 * scale,
      color,
      marginRight: layoutScale,
      marginTop: -4 * layoutScale,
    },
    sqrtSign: {
      fontFamily: CODE_FONT,
      fontSize,
      lineHeight: SQRT_LINE_HEIGHT * scale,
      color,
    },
    sqrtBody: {
      fontFamily: CODE_FONT,
      fontSize,
      lineHeight: SQRT_LINE_HEIGHT * scale,
      color,
    },
    sqrtRadicand: {
      borderTopWidth: StyleSheet.hairlineWidth * 2,
      borderTopColor: color,
      paddingTop: layoutScale,
      marginLeft: layoutScale,
    },
    vinculum: {
      alignSelf: "stretch",
      height: StyleSheet.hairlineWidth * 2,
      marginVertical: 2 * layoutScale,
      backgroundColor: color,
    },
  });
};
