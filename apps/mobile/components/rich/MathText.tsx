import { useMemo, type ReactNode } from "react";
import { StyleSheet, Text } from "react-native";

import { CODE_FONT } from "@/lib/fonts";
import { fixImplicitExponents } from "@/lib/normalizeImplicitMath";
import { parseSimpleLatex, type MathSegment } from "@/lib/mathText";
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
      return (
        <Text key={key} style={styles.sup}>
          {seg.value}
        </Text>
      );
    }
    if (seg.type === "sub") {
      return (
        <Text key={key} style={styles.sub}>
          {seg.value}
        </Text>
      );
    }
    if (seg.type === "frac") {
      return (
        <Text key={key}>
          {seg.num}/{seg.den}
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
  });
};
