import { ReactNode } from "react";
import { Text, View, type StyleProp, type TextStyle } from "react-native";

import { MathText } from "@/components/rich/MathText";
import { splitStreamCaret, StreamingCursor } from "@/components/StreamingCursor";
import { mathSizeOf, withGreenTicks } from "@/components/markdown/rules/textWithMath";
import { splitInlineMath } from "@/lib/markdown/preprocess";
import { workoutPart } from "@/lib/markdown/workoutSection";
import { typedScriptsAsMath } from "@/lib/math/typedScripts";
import type { Theme } from "@/lib/theme";

/** Prose and ``$...$`` math in one wrapping run, every piece in one colour. */
export function workoutInline(
  text: string,
  keyPrefix: string,
  textStyle: StyleProp<TextStyle>,
  color: string,
  tickColor?: string,
): ReactNode[] {
  const size = mathSizeOf(textStyle);
  // A power or a limit written in the words ("as x → 5^+") is drawn as one.
  return splitInlineMath(typedScriptsAsMath(text)).map((part, i) =>
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
 * A heading in bold at the margin, its maths drawn as maths ("Substitution $x = \tan t$",
 * "Solve for $t$"): a heading drawn as plain text showed the dollars and the LaTeX
 * (2026-11-11).
 */
export function workingHeading(
  text: string,
  key: string,
  label: StyleProp<TextStyle>,
  t: Theme,
  testID: string,
): ReactNode {
  const marked = splitStreamCaret(text);
  if (!marked.caret && !typedScriptsAsMath(marked.text).includes("$")) {
    return (
      <Text testID={testID} style={label}>
        {text}
      </Text>
    );
  }
  return (
    <View
      testID={testID}
      style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "baseline" }}
    >
      {workoutInline(marked.text.trim(), key, label, t.assistantText)}
      {marked.caret ? <StreamingCursor /> : null}
    </View>
  );
}

/**
 * A part's letter, drawn whole before what the part asks: squeezed with the meaning in a
 * row that does not wrap, Android broke "(c)" as "(c" over ")" (2026-11-13).
 */
export function partLabelText(label: string, body: StyleProp<TextStyle>): React.ReactElement {
  return (
    <Text testID="workout-part-label" style={[body, { flexShrink: 0 }]}>
      {`${label} `}
    </Text>
  );
}

/** A line's part letter as written ("(c)", "Part (b):") and what follows it. */
export function partLabel(state: string): { label: string; rest: string } | null {
  const line = state.trim();
  const part = workoutPart(line);
  if (!part) return null;
  return { label: line.slice(0, line.length - part.title.length).trimEnd(), rest: part.title };
}
