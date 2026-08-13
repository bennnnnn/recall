import { useMemo, type ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";

import { CODE_FONT } from "@/lib/fonts";
import { fixImplicitExponents } from "@/lib/normalizeImplicitMath";
import {
  MATH_TALL_LINE_HEIGHT,
  parseSimpleLatex,
  segmentsToPlain,
  type MathSegment,
} from "@/lib/mathText";
import { toSubscript, toSuperscript } from "@/lib/unicodeSupSub";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  latex: string;
  textColor?: string;
};

type Styles = ReturnType<typeof makeStyles>;

/** A single atomic token ("11", "-4", "2a") needs no disambiguating
 * parens in a stacked numerator/denominator; multi-term sides get parens. */
function isAtomicToken(plain: string): boolean {
  return /^[±+\-]?[a-zA-Z0-9]+$/.test(plain);
}

const FRAC_CHAR_PX = 9;
const FRAC_PAD_PX = 14;
const FRAC_STACK_HEIGHT = 40;

function fracStackSize(num: string, den: string): { width: number; height: number } {
  const chars = Math.max(num.length, den.length, 1);
  return { width: chars * FRAC_CHAR_PX + FRAC_PAD_PX, height: FRAC_STACK_HEIGHT };
}

function hasFracSegment(segments: MathSegment[]): boolean {
  for (const seg of segments) {
    if (seg.type === "frac") return true;
    if (seg.type === "sqrt" && hasFracSegment(seg.body)) return true;
  }
  return false;
}

function renderFracSide(
  segments: MathSegment[],
  keyPrefix: string,
  styles: Styles,
  paren: boolean,
): ReactNode {
  // Nested fraction → recurse with a View row. Everything else (text, sqrt,
  // scripts) flattens to one compact Text so we never put a bare string
  // under a View (RN invariant) and numerator/denominator stay fraction-sized.
  if (segments.some((s) => s.type === "frac")) {
    return (
      <View style={styles.fracSideRow}>
        {paren ? <Text style={styles.fracPart}>(</Text> : null}
        {renderSegments(segments, keyPrefix, styles, true)}
        {paren ? <Text style={styles.fracPart}>)</Text> : null}
      </View>
    );
  }
  const plain = segmentsToPlain(segments);
  return (
    <Text style={styles.fracPart}>
      {paren ? `(${plain})` : plain}
    </Text>
  );
}

function renderSegments(
  segments: MathSegment[],
  keyPrefix: string,
  styles: Styles,
  inView = false,
): ReactNode[] {
  return segments.map((seg, i) => {
    const key = `${keyPrefix}-${i}`;
    if (seg.type === "sup") {
      const uni = toSuperscript(seg.value);
      const node = uni ?? seg.value;
      return (
        <Text key={key} style={uni ? undefined : styles.sup}>
          {node}
        </Text>
      );
    }
    if (seg.type === "sub") {
      const uni = toSubscript(seg.value);
      const node = uni ?? seg.value;
      return (
        <Text key={key} style={uni ? undefined : styles.sub}>
          {node}
        </Text>
      );
    }
    if (seg.type === "frac") {
      // True stacked fraction with a vinculum (horizontal bar): numerator
      // above, bar, denominator below — nested View inside the outer Text
      // so it still flows inline. Line height is bumped when any frac is
      // present so the stack doesn't clip neighboring prose.
      const numPlain = segmentsToPlain(seg.num);
      const denPlain = segmentsToPlain(seg.den);
      const box = fracStackSize(numPlain, denPlain);
      return (
        <View
          key={key}
          style={[styles.fracStack, box]}
          testID="math-frac"
          collapsable={false}
        >
          {renderFracSide(seg.num, `${key}-n`, styles, !isAtomicToken(numPlain))}
          <View style={styles.vinculum} testID="math-vinculum" />
          {renderFracSide(seg.den, `${key}-d`, styles, !isAtomicToken(denPlain))}
        </View>
      );
    }
    if (seg.type === "sqrt") {
      return <Text key={key}>{segmentsToPlain([seg])}</Text>;
    }
    if (inView) {
      return (
        <Text key={key} style={styles.fracPart}>
          {seg.value}
        </Text>
      );
    }
    return seg.value;
  });
}

/** Inline math as native Text — must stay a Text node so it flows in paragraphs/lists. */
export function MathText({ latex, textColor }: Props) {
  const theme = useTheme();
  const styles = useMemo(() => makeStyles(theme, textColor), [theme, textColor]);
  const segments = useMemo(
    () => parseSimpleLatex(fixImplicitExponents(latex.trim())),
    [latex],
  );
  const tall = useMemo(() => hasFracSegment(segments), [segments]);

  if (!latex.trim()) return null;

  return (
    <Text style={[styles.base, tall && styles.baseWithFrac]}>
      {renderSegments(segments, "m", styles)}
    </Text>
  );
}

const makeStyles = (theme: Theme, textColor?: string) => {
  const color = textColor ?? theme.text;
  return StyleSheet.create({
    base: {
      fontFamily: CODE_FONT,
      fontSize: 16,
      lineHeight: 24,
      color,
    },
    // Room for a stacked fraction so the numerator doesn't kiss the line above.
    baseWithFrac: {
      lineHeight: MATH_TALL_LINE_HEIGHT,
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
    fracStack: {
      alignItems: "center",
      justifyContent: "center",
      marginHorizontal: 3,
    },
    fracSideRow: {
      flexDirection: "row",
      alignItems: "center",
    },
    fracPart: {
      fontFamily: CODE_FONT,
      fontSize: 11,
      lineHeight: 14,
      color,
      textAlign: "center",
    },
    // Vinculum — the straight horizontal fraction bar.
    vinculum: {
      alignSelf: "stretch",
      height: StyleSheet.hairlineWidth * 2,
      marginVertical: 2,
      backgroundColor: color,
    },
  });
};
