import { ReactNode } from "react";
import { Text, View, type StyleProp, type TextStyle } from "react-native";

import { MathText } from "@/components/rich/MathText";
import { splitStreamCaret, StreamingCursor } from "@/components/StreamingCursor";
import { mathSizeOf, withGreenTicks } from "@/components/markdown/rules/textWithMath";
import { splitInlineMath } from "@/lib/markdown/preprocess";
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
  if (!marked.caret && !marked.text.includes("$")) {
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
