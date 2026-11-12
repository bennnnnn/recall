import { ReactNode } from "react";
import { Text, View, type StyleProp, type TextStyle } from "react-native";

import { MathColumn, workingLinePull } from "@/components/rich/mathColumn";
import { MathText } from "@/components/rich/MathText";
import {
  splitStreamCaret,
  StreamingCursor,
} from "@/components/StreamingCursor";
import {
  type AstNode,
  astText,
  astTextWithBreaks,
  openingStrong,
  unwrapSingle,
} from "@/components/markdown/markdownAstHelpers";
import {
  type StyleMap,
  WORK_GAP,
  WORK_INDENT,
  WORK_RULE,
} from "@/components/markdown/markdownContentStyles";
import { mathSizeOf, withGreenTicks } from "@/components/markdown/rules/textWithMath";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { DYNAMIC_TYPE_MAX, Type, Weight } from "@/lib/type";
import { splitInlineMath } from "@/lib/markdown/preprocess";
import {
  askedLine,
  isAnswerHeading,
  isRequiredHeading,
  isSolutionHeading,
  isWorkingHeading,
  lawHeading,
  SOLUTION_HEADING,
  splitWorkoutNote,
  workoutHeading,
  workoutPart,
} from "@/lib/markdown/workoutSection";
import type { Theme } from "@/lib/theme";

const WORKOUT_LINE_KIDS = new Set(["text", "softbreak", "hardbreak"]);

/** Plain text and line breaks only: emphasis, links, or code keep the markdown renderer. */
function plainInline(node: AstNode): boolean {
  if (WORKOUT_LINE_KIDS.has(node.type ?? "")) return true;
  return node.type === "textgroup" && (node.children ?? []).every(plainInline);
}

/**
 * A workout section: a bold heading that ends its line, then one state per
 * line. The lines are rows of their own because a stacked fraction turns a
 * paragraph into a wrapping row, where a line break is lost.
 */
export function workoutSectionParts(
  node: AstNode,
): { heading: string; lines: string[] } | null {
  const kids = unwrapSingle(node).children ?? [];
  const strong = openingStrong(kids[0]);
  if (!strong) return null;
  const rest = kids.slice(1);
  // **Solution** stands alone: the sections after it are its working.
  const restText = rest.map((kid) => astTextWithBreaks(kid)).join("");
  if (
    !restText.trim() &&
    isSolutionHeading(splitStreamCaret(astText(strong)).text)
  ) {
    return { heading: SOLUTION_HEADING, lines: [] };
  }
  if (!rest.length || !rest.every(plainInline)) return null;
  const tail = rest.map((kid) => astTextWithBreaks(kid)).join("");
  if (!/^[ \t]*\n/.test(tail)) return null;
  const lines = tail
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) return null;
  // A law's own name over its formulas reaches here as one paragraph only in a
  // worked reply: elsewhere a bold line gets a paragraph of its own.
  const heading =
    workoutHeading(astText(strong)) ??
    lawHeading(astText(strong), lines[0] ?? "");
  return heading ? { heading, lines } : null;
}

/** A part label alone on its line in bold: ``**(a) Acceleration**``. */
export function workoutPartParts(
  node: AstNode,
): { letter: string; title: string } | null {
  const kids = unwrapSingle(node).children ?? [];
  const strong = openingStrong(kids[0]);
  if (!strong) return null;
  if (kids.slice(1).some((kid) => astTextWithBreaks(kid).trim())) return null;
  return workoutPart(splitStreamCaret(astText(strong)).text);
}

/** Prose and ``$...$`` math in one wrapping run, every piece in one colour. */
function workoutInline(
  text: string,
  keyPrefix: string,
  textStyle: StyleProp<TextStyle>,
  color: string,
  tickColor?: string,
): ReactNode[] {
  const size = mathSizeOf(textStyle);
  return splitInlineMath(text).map((part, i) =>
    part.type === "math" ? (
      <MathText
        scrollOverflow
        key={`${keyPrefix}-m-${i}`}
        latex={part.value}
        textColor={color}
        fontSize={size}
      />
    ) : (
      <Text key={`${keyPrefix}-t-${i}`} style={textStyle} selectable>
        {tickColor
          ? withGreenTicks(part.value, tickColor, `${keyPrefix}-${i}`)
          : part.value}
      </Text>
    ),
  );
}

/**
 * "where $v_0$ = initial speed, $g$ = …" in pieces, one per name, each ending with its comma:
 * drawn apart, a line could break between a symbol and its meaning ("…, m" / "= mass").
 */
function namingPieces(line: string): string[] {
  const pieces: string[] = [];
  let inMath = false;
  let start = 0;
  for (let i = 0; i < line.length; i += 1) {
    if (line[i] === "$") inMath = !inMath;
    else if (
      !inMath &&
      (line[i] === "," || line[i] === ";") &&
      line[i + 1] === " "
    ) {
      pieces.push(line.slice(start, i + 1));
      start = i + 2;
    }
  }
  pieces.push(line.slice(start));
  return pieces;
}

/** The last line holding maths; the last line when none does. */
function lastMathLine(lines: string[]): number {
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    if (/[$=≈]/.test(lines[index] ?? "")) return index;
  }
  return lines.length - 1;
}

/**
 * The thin rule Given and Required sit behind, and only they: the working inside Solution
 * (a formula under its name, Substitution, Steps, a numbered move) has none; its lines
 * start at the column Given's values do (`WORK_INDENT`).
 */
function workoutRule(t: Theme) {
  return {
    marginLeft: WORK_RULE.inset,
    paddingLeft: WORK_RULE.gap,
    borderLeftWidth: WORK_RULE.width,
    borderLeftColor: t.separator,
  } as const;
}

/**
 * A heading inside Solution (a formula's name, Substitution, a move): bold in the reply's
 * ink at the margin, its working indented under it. Bold as a model's own headings and
 * bold text are, so the server's and the model's replies read alike (November 2026).
 */
export function subheadingStyle(styles: StyleMap, t: Theme): StyleProp<TextStyle> {
  return [styles.body, styles.text, { ...Weight.bold, color: t.assistantText }];
}

// "Solve for $t$": a step of the working written as words, drawn as a move.
const SOLVE_FOR = /^Solve for\s/;

/**
 * One state of a section, its maths. Nothing is ever drawn at the right edge: a move
 * (`$2x = 8$ — subtract 3`) is a line of its own just above the maths it reached, drawn
 * as "Solve for $t$" is; a given or what is asked reads "$t$ (time)" on one row. A given's closing
 * "where" line names each symbol in secondary ink.
 */
function renderWorkoutLine(
  lineKey: string,
  line: string,
  { given, asked }: { given: boolean; asked: boolean },
  {
    body,
    noteStyle,
  }: { body: StyleProp<TextStyle>; noteStyle: StyleProp<TextStyle> },
  t: Theme,
): React.ReactElement {
  // While streaming, the caret's mark rides on the last line: draw the caret, never the mark.
  const marked = splitStreamCaret(line);
  // A given or what is asked is one line, its meaning beside it ("$t$ (time)"); only a
  // move's note is a line of its own.
  const { state, note } = splitWorkoutNote(
    asked || given ? askedLine(marked.text) : marked.text,
  );
  const naming = given && /^where\s/i.test(state);
  const move = !note && SOLVE_FOR.test(state);
  // Every line of a worked solution starts at the same left edge: a formula, its
  // substitution, a move and a given read down one column (a centred formula over
  // left-aligned substitution lines read as two layouts, November 2026). Words and
  // maths on a line share its baseline.
  const row = (
    <View
      key={lineKey}
      testID="workout-line"
      style={{
        flexDirection: "row",
        flexWrap: "wrap",
        alignItems: "baseline",
        justifyContent: "flex-start",
        flexShrink: 1,
      }}
    >
      {naming ? (
        namingPieces(state).map((piece, pieceIndex) => (
          <View
            key={`${lineKey}-name-${pieceIndex}`}
            testID="workout-naming"
            // A symbol stays beside its meaning; a long meaning wraps after it.
            style={{
              flexDirection: "row",
              alignItems: "baseline",
              maxWidth: "100%",
              marginRight: Space.xxs,
            }}
          >
            {workoutInline(
              piece,
              `${lineKey}-name-${pieceIndex}`,
              [noteStyle, { flexShrink: 1 }],
              t.textSecondary,
            )}
          </View>
        ))
      ) : (
        <View
          testID={asked ? "workout-asked" : move ? "workout-move" : undefined}
          // The unknown stays beside its meaning on one line; a long meaning wraps
          // inside it, never onto a row of its own.
          style={{
            flexDirection: "row",
            flexWrap: asked ? undefined : "wrap",
            alignItems: "baseline",
            maxWidth: "100%",
          }}
        >
          {workoutInline(
            state,
            `${lineKey}-state`,
            move ? [noteStyle, { flexShrink: 1 }] : [body, { flexShrink: 1 }],
            move ? t.textSecondary : t.assistantText,
            move ? undefined : t.success,
          )}
        </View>
      )}
      {marked.caret ? <StreamingCursor key={`${lineKey}-caret`} /> : null}
    </View>
  );
  if (!note) return row;
  return (
    <View key={lineKey} testID="workout-step" style={{ gap: Space.xxs }}>
      <View
        testID="workout-move"
        style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "baseline" }}
      >
        {workoutInline(note, `${lineKey}-note`, noteStyle, t.textSecondary, t.success)}
      </View>
      {row}
    </View>
  );
}

/**
 * Working inside Solution, step by step: the section's own heading over its first lines, and
 * each "Solve for $d$" a heading of its own, bold at the margin, over the lines it reaches. A
 * grey "Solve for" between two equations read as part of the calculation (November 2026).
 */
function renderWorkingSteps(
  key: string,
  section: { heading: string; lines: string[] },
  lines: React.ReactElement[],
  styles: StyleMap,
  t: Theme,
): React.ReactElement {
  const label = subheadingStyle(styles, t);
  const size = mathSizeOf(styles.body);
  // A long line moves left into the indent before it scrolls; the others keep the column.
  const fitted = (index: number): React.ReactElement => {
    const pull = workingLinePull(splitStreamCaret(section.lines[index] ?? "").text, WORK_INDENT, size);
    const line = lines[index]!;
    if (pull <= 0) return line;
    // Its formulas are told the column they now start in, so they scroll only past the line.
    return (
      <View key={`${key}-pull-${index}`} style={{ marginLeft: -pull }}>
        <MathColumn inset={-pull}>{line}</MathColumn>
      </View>
    );
  };
  const steps: { heading: ReactNode; lines: React.ReactElement[] }[] = [
    {
      heading: (
        <Text testID="workout-subheading" style={label}>
          {section.heading}
        </Text>
      ),
      lines: [],
    },
  ];
  section.lines.forEach((line, index) => {
    const marked = splitStreamCaret(line);
    if (!SOLVE_FOR.test(marked.text.trim())) {
      steps[steps.length - 1]!.lines.push(fitted(index));
      return;
    }
    steps.push({
      heading: (
        <View
          testID="workout-subheading"
          style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "baseline" }}
        >
          {workoutInline(marked.text.trim(), `${key}-solve-${index}`, label, t.assistantText)}
          {marked.caret ? <StreamingCursor /> : null}
        </View>
      ),
      lines: [],
    });
  });
  return (
    <View key={key} testID="workout-section" style={[styles.paragraphRun, { gap: Space.md }]}>
      {steps.map((step, index) => (
        <View key={`${key}-step-${index}`}>
          {step.heading}
          {step.lines.length ? (
            <View
              testID="workout-body"
              style={{ gap: Space.xs, marginTop: WORK_GAP, paddingLeft: WORK_INDENT }}
            >
              <MathColumn inset={WORK_INDENT}>{step.lines}</MathColumn>
            </View>
          ) : null}
        </View>
      ))}
    </View>
  );
}

/**
 * A worked-solution section, at one of two levels. Given, Required, Solution and Answer
 * are sections: a heading at the margin, Given's and Required's lines behind a thin rule.
 * Every other section (a formula under its name, Substitution, Steps) is working inside
 * Solution: a smaller heading in secondary ink and its lines, with no rule, whoever wrote
 * the reply and whether or not it has a **Solution** heading; its lines start at the
 * left edge every other line of the solution starts at. Each given is
 * its own line, and a closing "where v₀ = initial speed, …" line names them in secondary
 * ink. The last line of maths in a written-out answer sits in a white, bordered box,
 * outside the rule (the lines before it are working, a sentence after it stays below). A
 * card the server landed is its own ```answer fence and never reaches here; this draws
 * older replies the same way.
 */
export function renderWorkoutSection(
  key: string,
  section: { heading: string; lines: string[] },
  styles: StyleMap,
  t: Theme,
): React.ReactElement {
  const body = [styles.body, styles.text, { color: t.assistantText }];
  const noteStyle = [
    styles.text,
    { ...Type.secondary, color: t.textSecondary },
  ];
  const given = section.heading === "Given";
  const asked = isRequiredHeading(section.heading);
  const answer = isAnswerHeading(section.heading);
  const working = isWorkingHeading(section.heading);
  const boxed = answer ? lastMathLine(section.lines) : -1;
  const lines = section.lines.map((line, index) =>
    renderWorkoutLine(
      `${key}-line-${index}`,
      line,
      { given, asked },
      { body, noteStyle },
      t,
    ),
  );
  if (working) {
    return renderWorkingSteps(key, section, lines, styles, t);
  }
  const heading = (
    <Text
      testID="workout-heading"
      style={[
        styles.body,
        styles.text,
        { ...Weight.bold, color: t.assistantText },
      ]}
    >
      {section.heading}
    </Text>
  );
  // **Solution** has no lines: the sections below it are its working.
  if (!section.lines.length) {
    return (
      <View key={key} testID="workout-section" style={styles.paragraphRun}>
        {heading}
      </View>
    );
  }
  return (
    <View
      key={key}
      testID="workout-section"
      style={[styles.paragraphRun, { gap: Space.xs }]}
    >
      {heading}
      <View
        testID="workout-body"
        // Given and Required sit behind a rule; the Answer's box needs none.
        style={answer ? { gap: Space.xs } : { ...workoutRule(t), gap: Space.xs }}
      >
        {answer ? (
          <>
            {lines.slice(0, boxed)}
            <View
              testID="workout-answer"
              style={{
                alignItems: "center",
                backgroundColor: t.bg,
                borderWidth: 1,
                borderColor: t.borderStrong,
                borderRadius: Radius.md,
                paddingVertical: Space.sm,
                paddingHorizontal: Space.md,
              }}
            >
              {lines[boxed]}
            </View>
            {lines.slice(boxed + 1)}
          </>
        ) : (
          lines
        )}
      </View>
    </View>
  );
}

/** A question part: its letter in a pill, then what the part finds. */
export function renderWorkoutPart(
  key: string,
  part: { letter: string; title: string },
  styles: StyleMap,
  t: Theme,
): React.ReactElement {
  return (
    <View
      key={key}
      testID="workout-part"
      style={[
        styles.paragraphRun,
        { flexDirection: "row", alignItems: "center", gap: Space.xs },
      ]}
    >
      <View
        style={{
          // A pill once large text makes the letter wider than 22pt.
          minWidth: 22,
          minHeight: 22,
          paddingHorizontal: Space.xxs,
          borderRadius: Radius.full,
          backgroundColor: t.accentLight,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Text
          style={{ ...Type.caption, ...Weight.bold, color: t.accent }}
          maxFontSizeMultiplier={DYNAMIC_TYPE_MAX}
        >
          {part.letter}
        </Text>
      </View>
      <View
        testID="workout-part-title"
        style={{
          flex: 1,
          flexDirection: "row",
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        {workoutInline(
          part.title,
          `${key}-part`,
          [styles.body, styles.text, { ...Weight.bold, color: t.accent }],
          t.accent,
        )}
      </View>
    </View>
  );
}
