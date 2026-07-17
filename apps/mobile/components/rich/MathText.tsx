import { useMemo, type ReactNode } from "react";
import { StyleSheet, Text } from "react-native";

import { CODE_FONT } from "@/lib/fonts";
import { fixImplicitExponents } from "@/lib/normalizeImplicitMath";
import { parseSimpleLatex, segmentsToPlain, type MathSegment } from "@/lib/mathText";
import { toSubscript, toSuperscript } from "@/lib/unicodeSupSub";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  latex: string;
  textColor?: string;
};

/** A single atomic token ("11", "-4", "2a") needs no disambiguating
 * parens when dropped into a single-line "num⁄den"; anything with an
 * internal operator, a space, or more than one segment does. */
function isAtomicToken(plain: string): boolean {
  return /^[±+\-]?[a-zA-Z0-9]+$/.test(plain);
}

function renderSegments(
  segments: MathSegment[],
  keyPrefix: string,
  styles: ReturnType<typeof makeStyles>,
): ReactNode[] {
  return segments.map((seg, i) => {
    const key = `${keyPrefix}-${i}`;
    if (seg.type === "sup") {
      // Prefer a real Unicode superscript (renders raised in plain text, no
      // KaTeX WebView needed). Fall back to styled smaller Text when a char
      // has no Unicode superscript — better than nothing.
      const uni = toSuperscript(seg.value);
      if (uni) return <Text key={key}>{uni}</Text>;
      return (
        <Text key={key} style={styles.sup}>
          {seg.value}
        </Text>
      );
    }
    if (seg.type === "sub") {
      const uni = toSubscript(seg.value);
      if (uni) return <Text key={key}>{uni}</Text>;
      return (
        <Text key={key} style={styles.sub}>
          {seg.value}
        </Text>
      );
    }
    if (seg.type === "frac") {
      // Deliberately single-line — never stack numerator/denominator across
      // two rows with an embedded "\n". React Native's Text layout doesn't
      // grow the *surrounding* paragraph's line height to fit a taller
      // nested multi-line run, so a stacked fraction only looks right when
      // it's the sole content of its own block (MathBlock's display-math
      // case); inline among sibling prose/other fractions (numbered steps,
      // "you can check" bullets, a plain "3/4 + 1/6") the stack overlapped
      // the text immediately above and below it.
      const numPlain = segmentsToPlain(seg.num);
      const denPlain = segmentsToPlain(seg.den);
      const numUni = toSuperscript(numPlain);
      const denUni = toSubscript(denPlain);
      if (numUni && denUni) {
        return (
          <Text key={key}>
            {numUni}
            <Text style={styles.fracSlash}>⁄</Text>
            {denUni}
          </Text>
        );
      }
      // Numerator/denominator too complex for Unicode super/subscript
      // digits (nested fractions, roots, multi-term expressions, …) — fall
      // back to plain-size text on one line, parenthesizing anything that
      // isn't a single atomic token so "a+b/c+d" can't be misread as
      // "a + (b/c) + d".
      const numNode = isAtomicToken(numPlain) ? (
        renderSegments(seg.num, `${key}-n`, styles)
      ) : (
        <>({renderSegments(seg.num, `${key}-n`, styles)})</>
      );
      const denNode = isAtomicToken(denPlain) ? (
        renderSegments(seg.den, `${key}-d`, styles)
      ) : (
        <>({renderSegments(seg.den, `${key}-d`, styles)})</>
      );
      return (
        <Text key={key}>
          {numNode}
          <Text style={styles.fracSlash}>/</Text>
          {denNode}
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

  if (!latex.trim()) return null;

  return (
    <Text style={styles.base}>
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
    sup: {
      fontSize: 11,
      lineHeight: 18,
      color,
    },
    sub: {
      fontSize: 11,
      lineHeight: 18,
      color,
    },
    // Single-line fraction slash — never a two-row stack (see the "frac"
    // case in renderSegments above for why).
    fracSlash: {
      color,
      marginHorizontal: 1,
    },
  });
};
