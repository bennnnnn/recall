import React from "react";
import { StyleSheet, View } from "react-native";

import { WORK_INDENT } from "@/components/markdown/markdownContentStyles";
import { formulaLinesIndent } from "@/components/rich/mathColumn";
import { MathSvgView } from "@/components/rich/MathSvgView";
import { restoreMathEscapes, splitMathLines } from "@/lib/math/text";
import { rewriteSolutionSeparatorBars } from "@/lib/math/solutionBars";
import { stripEmbeddedDollarWraps, stripRedundantDollarWrap } from "@/lib/math/fenceRetag";
import { useTheme } from "@/lib/theme";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";

/**
 * A display equation. `indent` is a reply's own ```math / `$$` block: working, so it starts
 * in the column a worked solution's lines do (`WORK_INDENT`, November 2026); one inside a
 * card or a sentence keeps its place.
 */
export const MathBlock = React.memo(function MathBlock({
  latex,
  indent = false,
  lineIndent,
}: {
  latex: string;
  indent?: boolean;
  /** A line of a block of several: the indent the block's widest line leaves. */
  lineIndent?: number;
}) {
  const theme = useTheme();
  const trimmed = rewriteSolutionSeparatorBars(
    stripEmbeddedDollarWraps(stripRedundantDollarWrap(restoreMathEscapes(latex.trim()))),
  );
  if (!trimmed) return null;

  // A fence body with multiple independent equations (one per line) must
  // render each as its own block — a single render call concatenates every
  // line into one expression with no separator. splitMathLines is
  // environment-aware: it returns the whole body as one entry when it
  // contains a \begin{…} (aligned/cases/matrix/…), so multi-line
  // environments render as one MathJax-SVG block instead of being shattered
  // into per-row parse errors.
  const lines = splitMathLines(trimmed);
  if (lines.length > 1) {
    // The lines read down one column: each starts where the widest leaves room.
    const shared = indent ? formulaLinesIndent(lines, WORK_INDENT, Type.reading.fontSize) : 0;
    return (
      <View style={styles.wrap}>
        {lines.map((line, i) => (
          // Index disambiguates a restated line (e.g. `x = 4` twice); content
          // alone collides the same way sibling math fences do without tokenIndex.
          <MathBlock key={`line:${i}:${line}`} latex={line} lineIndent={shared} />
        ))}
      </View>
    );
  }

  // The indent is the formula's own: a long one gives it up before it scrolls.
  return (
    <View style={styles.wrap}>
      <MathSvgView
        latex={trimmed}
        textColor={theme.text}
        minHeight={48}
        align="start"
        indent={lineIndent ?? (indent ? WORK_INDENT : 0)}
      />
    </View>
  );
});

const styles = StyleSheet.create({
  wrap: {
    marginVertical: Space.xs,
    alignSelf: "stretch",
    width: "100%",
  },
});
