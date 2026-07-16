import { useMemo, type ReactNode } from "react";
import { StyleSheet, Text } from "react-native";

import { CODE_FONT } from "@/lib/fonts";
import { fixImplicitExponents } from "@/lib/normalizeImplicitMath";
import { parseSimpleLatex, type MathSegment } from "@/lib/mathText";
import { toSubscript, toSuperscript } from "@/lib/unicodeSupSub";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  latex: string;
  textColor?: string;
};

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
      // The fraction bar is a `borderBottomWidth` on the numerator Text —
      // it spans the numerator's actual rendered width exactly, regardless
      // of font, so a wide fraction like the quadratic formula
      // ((-4 ± √(...)) / 2) gets a proper long bar instead of the single
      // "─" glyph that used to read as a tiny dot over one digit. Stays a
      // Text node so the fraction still flows inline in prose.
      return (
        <Text key={key} style={styles.frac}>
          <Text style={styles.fracNum}>{seg.num}</Text>
          {"\n"}
          <Text style={styles.fracDen}>{seg.den}</Text>
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
    frac: {
      textAlign: "center",
      lineHeight: 13,
      paddingHorizontal: 1,
    },
    fracNum: {
      fontSize: 11,
      lineHeight: 13,
      color,
      // The fraction bar — a hairline border under the numerator spans its
      // exact rendered width (no char-count heuristic), so wide fractions
      // get a proper long bar instead of a one-glyph dash.
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderColor: color,
      paddingBottom: 1,
    },
    fracDen: {
      fontSize: 11,
      lineHeight: 13,
      color,
    },
  });
};
