import { ReactNode } from "react";
import { Text, View, type StyleProp, type TextStyle } from "react-native";

import { MathText } from "@/components/rich/MathText";
import {
  type AstNode,
  astText,
  astTextWithBreaks,
  openingStrong,
  unwrapSingle,
} from "@/components/markdown/markdownAstHelpers";
import type { StyleMap } from "@/components/markdown/markdownContentStyles";
import { withGreenTicks } from "@/components/markdown/rules/textWithMath";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { DYNAMIC_TYPE_MAX, Type, Weight } from "@/lib/type";
import { splitInlineMath } from "@/lib/markdown/preprocess";
import { splitWorkoutNote, workoutHeading, workoutPart } from "@/lib/markdown/workoutSection";
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
export function workoutSectionParts(node: AstNode): { heading: string; lines: string[] } | null {
  const kids = unwrapSingle(node).children ?? [];
  const strong = openingStrong(kids[0]);
  if (!strong) return null;
  const heading = workoutHeading(astText(strong));
  if (!heading) return null;
  const rest = kids.slice(1);
  if (!rest.length || !rest.every(plainInline)) return null;
  const tail = rest.map((kid) => astTextWithBreaks(kid)).join("");
  if (!/^[ \t]*\n/.test(tail)) return null;
  const lines = tail
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.length ? { heading, lines } : null;
}

/** A part label alone on its line in bold: ``**(a) Acceleration**``. */
export function workoutPartParts(node: AstNode): { letter: string; title: string } | null {
  const kids = unwrapSingle(node).children ?? [];
  const strong = openingStrong(kids[0]);
  if (!strong) return null;
  if (kids.slice(1).some((kid) => astTextWithBreaks(kid).trim())) return null;
  return workoutPart(astText(strong));
}

/** Prose and ``$...$`` math in one wrapping run, every piece in one colour. */
function workoutInline(
  text: string,
  keyPrefix: string,
  textStyle: StyleProp<TextStyle>,
  color: string,
  tickColor?: string,
): ReactNode[] {
  return splitInlineMath(text).map((part, i) =>
    part.type === "math" ? (
      <MathText scrollOverflow key={`${keyPrefix}-m-${i}`} latex={part.value} textColor={color} />
    ) : (
      <Text key={`${keyPrefix}-t-${i}`} style={textStyle} selectable>
        {tickColor ? withGreenTicks(part.value, tickColor, `${keyPrefix}-${i}`) : part.value}
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
    else if (!inMath && (line[i] === "," || line[i] === ";") && line[i + 1] === " ") {
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

/** Given and Find, what the question states and asks, sit behind a thin rule. */
const RULED_SECTIONS: ReadonlySet<string> = new Set(["Given", "Find"]);
const RULE_WIDTH = 2;

/**
 * A worked-solution section. The heading stays at the margin and its lines are
 * indented under it: Given and Find behind a thin rule, the working without one,
 * every section's lines starting at the same edge. Each given is its own line,
 * and a closing "where v₀ = initial speed, …" line names them in secondary ink.
 * A move's note sits at the right edge, and the last line of maths in a
 * written-out answer sits in a tinted box (the lines before it are working, a
 * sentence after it stays below). A card the server landed is its own
 * ```answer fence and never reaches here; this draws older replies the same way.
 */
export function renderWorkoutSection(
  key: string,
  section: { heading: string; lines: string[] },
  styles: StyleMap,
  t: Theme,
): React.ReactElement {
  const body = [styles.body, styles.text, { color: t.assistantText }];
  const noteStyle = [styles.text, { ...Type.secondary, color: t.textSecondary }];
  const given = section.heading === "Given";
  const answer = section.heading === "Answer";
  const boxed = answer ? lastMathLine(section.lines) : -1;
  const lines = section.lines.map((line, index) => {
    const { state, note } = splitWorkoutNote(line);
    const lineKey = `${key}-line-${index}`;
    const naming = given && /^where\s/i.test(state);
    return (
      <View
        key={lineKey}
        testID="workout-line"
        style={{
          flexDirection: "row",
          flexWrap: "wrap",
          alignItems: "center",
          columnGap: Space.sm,
          rowGap: Space.xxs,
        }}
      >
        <View
          style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center", flexShrink: 1 }}
        >
          {naming
            ? namingPieces(state).map((piece, pieceIndex) => (
                <View
                  key={`${lineKey}-name-${pieceIndex}`}
                  testID="workout-naming"
                  // A symbol stays beside its meaning; a long meaning wraps after it.
                  style={{ flexDirection: "row", alignItems: "center", maxWidth: "100%", marginRight: Space.xxs }}
                >
                  {workoutInline(piece, `${lineKey}-name-${pieceIndex}`, [noteStyle, { flexShrink: 1 }], t.textSecondary)}
                </View>
              ))
            : workoutInline(state, `${lineKey}-state`, body, t.assistantText, t.success)}
        </View>
        {note ? (
          <View
            testID="workout-note"
            style={{
              // Pushed to the right edge; on its own line when the row is full.
              marginLeft: given ? 0 : "auto",
              flexDirection: "row",
              flexWrap: "wrap",
              alignItems: "center",
              justifyContent: "flex-end",
              flexShrink: 1,
            }}
          >
            {workoutInline(note, `${lineKey}-note`, noteStyle, t.textSecondary, t.success)}
          </View>
        ) : null}
      </View>
    );
  });
  return (
    <View key={key} testID="workout-section" style={[styles.paragraphRun, { gap: Space.xs }]}>
      <Text
        testID="workout-heading"
        style={[styles.body, styles.text, { ...Weight.semibold, color: t.assistantText }]}
      >
        {section.heading}
      </Text>
      <View
        testID="workout-body"
        // Given and Find sit behind a rule; the working keeps its edge without one,
        // and the Answer's tinted box needs neither.
        style={
          answer
            ? { gap: Space.xs }
            : RULED_SECTIONS.has(section.heading)
              ? {
                  marginLeft: Space.xxs,
                  paddingLeft: Space.sm,
                  borderLeftWidth: RULE_WIDTH,
                  borderLeftColor: t.separator,
                  gap: Space.xs,
                }
              : { marginLeft: Space.xxs, paddingLeft: Space.sm + RULE_WIDTH, gap: Space.xs }
        }
      >
        {answer ? (
          <>
            {lines.slice(0, boxed)}
            <View
              testID="workout-answer"
              style={{
                alignItems: "center",
                backgroundColor: t.accentLight,
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
        style={{ flex: 1, flexDirection: "row", flexWrap: "wrap", alignItems: "center" }}
      >
        {workoutInline(
          part.title,
          `${key}-part`,
          [styles.body, styles.text, { ...Weight.semibold, color: t.accent }],
          t.accent,
        )}
      </View>
    </View>
  );
}
