/**
 * Glyph runs inside native math: operator words stay upright, letter runs are
 * italic variables, and the glyphs the math face lacks or spaces differently
 * (negated relations, blackboard letters, primes, norms) get their own Text.
 */
import { type ReactNode } from "react";
import { Platform, Text, type TextStyle } from "react-native";

import { splitOperatorPads } from "@/lib/math/layout";
import {
  AMS_ONLY_CHARS,
  BLACKBOARD_LATIN,
  isUprightMathWord,
  italicLeanEm,
  MATH_NOT_GLYPH,
  NEGATED_RELATION,
  NORM_ADVANCE_EM,
  notSlashSpacing,
  primeRun,
} from "@/lib/math/glyphs";

/** The size a run draws at: layout pixels per em, and the device font scale. */
type RunMetrics = { em: number; fontScale: number };

/**
 * Operator spacing for a run; `space: false` keeps a script's operators tight. `edge`: the
 * run's Texts are boxes of their own (children of a View, not nested in a Text), and a box
 * cuts off the ink an italic letter leans past its advance (`P` drew as `F`), so each that
 * ends on one keeps its italic correction as padding and gives it back as a negative
 * margin: the ink is whole and nothing beside it moves. `lean`: the run ends its row, and
 * its last letter gets that room for real (the composer's draft, whose caret follows).
 */
export type RunPad = RunMetrics & { leadingAtom: boolean; space?: boolean; lean?: boolean; edge?: boolean };

/** A run drawn without padding measures its glyphs at the stylesheet's 16px. */
const UNPADDED_METRICS: RunMetrics = { em: 16, fontScale: 1 };

// Latin and Greek letters make separate runs: `\sin\theta` reads "sinθ", and as one run
// the function name was drawn italic with its angle, a product of four variables.
const MATH_LETTER_RUN = /[A-Za-z]+|[Ͱ-Ͽ]+/g;

/** The style that keeps a box's last italic letter whole: room for its lean (`leanEm`,
 * `italicLeanEm`), and with `give` that room handed back as a negative margin, so the box
 * takes its advance alone. */
export function italicEdge(leanEm: number, em: number, fontScale: number, give: boolean): TextStyle | null {
  const lean = leanEm * em * fontScale;
  if (lean <= 0) return null;
  return give ? { paddingRight: lean, marginRight: -lean } : { paddingRight: lean };
}

export function renderNonVariableRun(
  value: string,
  key: string,
  glyphStyle: object,
  metrics: RunMetrics,
): ReactNode[] {
  return Array.from(value).map((ch, i) => renderMathGlyph(ch, `${key}-g${i}`, glyphStyle, metrics));
}

/**
 * The letterSpacing, in layout pixels, of one em of the run. iOS sets a Text's letterSpacing
 * as written, while the text itself grows with the reader's text size; Android grows the
 * letterSpacing with the text. Scaled again there, a pull meant to lay one glyph on another
 * missed it at any text size but the default.
 */
function letterSpacingPx(metrics: RunMetrics): number {
  return Platform.OS === "android" ? metrics.em : metrics.em * metrics.fontScale;
}

function renderMathGlyph(
  ch: string,
  key: string,
  glyphStyle: object,
  metrics: RunMetrics,
): ReactNode {
  const negated = NEGATED_RELATION[ch];
  if (negated) {
    const px = letterSpacingPx(metrics);
    const spacing = notSlashSpacing(Platform.OS === "android");
    return (
      <Text key={key} testID="math-negated" accessibilityLabel={ch}>
        {spacing.lead == null ? null : <Text style={{ letterSpacing: spacing.lead * px }}>{"\u00a0"}</Text>}
        <Text style={{ letterSpacing: spacing.slash * px }}>{MATH_NOT_GLYPH}</Text>
        {negated.base}
      </Text>
    );
  }
  const blackboard = BLACKBOARD_LATIN[ch];
  if (blackboard) {
    return (
      <Text key={key} testID="math-blackboard" style={glyphStyle}>
        {blackboard}
      </Text>
    );
  }
  if (AMS_ONLY_CHARS.has(ch)) {
    return (
      <Text key={key} style={glyphStyle}>
        {ch}
      </Text>
    );
  }
  const primes = primeRun(ch);
  if (primes) return primes;
  // A formula is one word in the line: "(T = mg)" drew "(T" on one line and "= mg)"
  // on the next. A no-break space measures as a space (layout.ts) but never wraps.
  if (ch === " ") return "\u00a0";
  if (ch === "-") return "−";
  if (ch === "·") return "⋅";
  if (ch === "‖") {
    const pull = (0.8 - NORM_ADVANCE_EM) * letterSpacingPx(metrics);
    return (
      <Text key={key} testID="math-norm" style={{ letterSpacing: -pull / 2 }}>
        ||
      </Text>
    );
  }
  return ch;
}

export function renderMathRun(
  value: string,
  key: string,
  textStyle: object,
  glyphStyle: object,
  variableStyle: object,
  testID?: string,
  pad?: RunPad,
): ReactNode {
  const pieces = pad && pad.space !== false
    ? splitOperatorPads(value, pad.leadingAtom)
    : [{ text: value, leftEm: 0, rightEm: 0 }];
  const metrics = pad ?? UNPADDED_METRICS;
  const runs = pieces.map((piece, pieceIndex) => {
    const pieceKey = pieces.length === 1 ? key : `${key}-p${pieceIndex}`;
    const children: ReactNode[] = [];
    let cursor = 0;
    let variableIndex = 0;
    for (const match of piece.text.matchAll(MATH_LETTER_RUN)) {
      const start = match.index ?? 0;
      if (start > cursor) {
        children.push(
          ...renderNonVariableRun(
            piece.text.slice(cursor, start),
            `${pieceKey}-t${cursor}`,
            glyphStyle,
            metrics,
          ),
        );
      }
      const word = match[0];
      children.push(
        isUprightMathWord(word) ? word : (
          <Text
            key={`${pieceKey}-v${variableIndex}`}
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
    if (cursor < piece.text.length) {
      children.push(
        ...renderNonVariableRun(
          piece.text.slice(cursor),
          `${pieceKey}-t${cursor}`,
          glyphStyle,
          metrics,
        ),
      );
    }
    // Padding, not margin: nested Text on iOS ignores margin, so the
    // measured operator space would never appear. A box's italic edge is the one margin:
    // only a box takes it. An operator's space after the letter is room enough.
    const lean = pad?.lean === true && pieceIndex === pieces.length - 1;
    const edge = !lean && pad?.edge === true && piece.rightEm === 0;
    const leanPx = pad && (lean || edge) ? italicLeanEm(piece.text) * pad.em * pad.fontScale : 0;
    const margin = pad
      ? {
          paddingLeft: piece.leftEm * pad.em * pad.fontScale,
          paddingRight: piece.rightEm * pad.em * pad.fontScale + leanPx,
          ...(edge && leanPx > 0 ? { marginRight: -leanPx } : null),
        }
      : null;
    return (
      <Text key={pieceKey} style={[textStyle, margin]} testID={pieces.length === 1 ? testID : undefined}>
        {children}
      </Text>
    );
  });
  if (runs.length === 1) return runs[0];
  return runs;
}
