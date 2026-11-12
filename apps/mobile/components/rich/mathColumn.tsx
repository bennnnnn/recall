import { createContext, type ReactElement, type ReactNode, useContext } from "react";
import { Dimensions, PixelRatio, View } from "react-native";

import { scaled } from "@/components/rich/mathText/context";
import { splitInlineMath } from "@/lib/markdown/inlineMath";
import { splitWorkoutNote } from "@/lib/markdown/workoutSection";
import { fittedIndent, layoutMath } from "@/lib/math/layout";
import { fixImplicitExponents } from "@/lib/math/normalizeImplicit";
import { parseSimpleLatex } from "@/lib/math/text";

const ColumnInset = createContext(0);

/**
 * Draws its children `inset` points in from the reply's left edge: a worked solution's
 * lines start at `WORK_INDENT`. A formula there has that much less room before it reaches
 * the right edge, so it scrolls when it is wider than what is left; judged against the whole
 * column, a line of working 30 points too wide was cut off at the edge ("∫cos((").
 */
export function MathColumn({ inset, children }: { inset: number; children: ReactNode }) {
  const outer = useContext(ColumnInset);
  return <ColumnInset.Provider value={outer + inset}>{children}</ColumnInset.Provider>;
}

/** How far in from the reply's left edge the formula is drawn. */
export function useMathColumnInset(): number {
  return useContext(ColumnInset);
}

/**
 * The indent for working lines that are each one formula (`latexLines`), at the size and
 * text scale ``MathText`` draws them: `indent` while the widest fits after it, less as it
 * grows (``fittedIndent``). Read outside a component (a markdown rule), so the window's
 * size and the text scale are read here, as ``useWindowDimensions`` would give them.
 */
export function formulaLinesIndent(latexLines: string[], indent: number, fontSize: number): number {
  const fontScale = PixelRatio.getFontScale();
  const widest = Math.max(0, ...latexLines.map((latex) => formulaWidth(latex, fontSize, fontScale)));
  return fittedIndent(indent, widest, Dimensions.get("window").width);
}

function formulaWidth(latex: string, fontSize: number, fontScale: number): number {
  return scaled(layoutMath(parseSimpleLatex(fixImplicitExponents(latex.trim())), fontSize).width, fontScale);
}

/**
 * How far a line of working (words and ``$…$`` maths, as written) moves left into its
 * column's `indent` so its widest formula fits the line before it scrolls; 0 while it fits
 * after the indent. Only formulas scroll: words wrap, and a move's note (" — subtract 3")
 * has a row of its own, so neither is measured.
 */
function workingLinePull(line: string, indent: number, fontSize: number): number {
  const fontScale = PixelRatio.getFontScale();
  const formulas = splitInlineMath(splitWorkoutNote(line).state).filter((part) => part.type === "math");
  const widest = Math.max(0, ...formulas.map((part) => formulaWidth(part.value, fontSize, fontScale)));
  return indent - fittedIndent(indent, widest, Dimensions.get("window").width);
}

/**
 * A line of working moved left into its column's `indent` when it would not fit after it
 * (``workingLinePull``). Its formulas are told the column they now start in, so they scroll
 * only past the line. A line that fits is returned as it is.
 */
export function fitWorkingLine(line: ReactElement, text: string, indent: number, fontSize: number): ReactElement {
  const pull = workingLinePull(text, indent, fontSize);
  if (pull <= 0) return line;
  return (
    <View key={line.key ?? undefined} style={{ marginLeft: -pull }}>
      <MathColumn inset={-pull}>{line}</MathColumn>
    </View>
  );
}
