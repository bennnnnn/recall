import { ReactNode } from "react";
import { StyleSheet, Text, View, type StyleProp, type TextStyle } from "react-native";

import { MathColumn } from "@/components/rich/mathColumn";
import { MathText } from "@/components/rich/MathText";
import { splitStreamCaret } from "@/components/StreamingCursor";
import {
  type AstNode,
  astText,
  astTextWithBreaks,
  openingStrong,
  unwrapSingle,
} from "@/components/markdown/markdownAstHelpers";
import {
  STEP_BADGE,
  STEP_LABEL_INSET,
  WORK_GAP,
  type StyleMap,
  WORK_INDENT,
} from "@/components/markdown/markdownContentStyles";
import { mathSizeOf } from "@/components/markdown/rules/textWithMath";
import { StepBadge } from "@/components/markdown/rules/stepBadge";
import { subheadingStyle } from "@/components/markdown/rules/workout";
import { Space } from "@/lib/space";
import { DYNAMIC_TYPE_MAX, Type, Weight } from "@/lib/type";
import { splitInlineMath } from "@/lib/markdown/preprocess";
import type { Theme } from "@/lib/theme";

const LESSON_STEP_RE = /^(\d+)\.\s+(\S[\s\S]*)$/;

/** A generated lesson heading, then each equation of that move on its own line. */
export function lessonStepParts(
  node: AstNode,
): { n: string; label: string; reason: string | null; formulas: string[] } | null {
  // A hard break splits the paragraph into textgroups: [heading — rule, $a$]
  // [break] [$b$]. Read them as one run, or a rule note hides the badge.
  const kids = (unwrapSingle(node).children ?? []).flatMap((kid) =>
    kid.type === "textgroup" ? (kid.children ?? []) : [kid],
  );
  const strong = openingStrong(kids[0]);
  if (!strong) return null;
  // A streaming caret's mark is never part of the step.
  const match = LESSON_STEP_RE.exec(splitStreamCaret(astText(strong)).text.trim());
  if (!match) return null;

  const tail = splitStreamCaret(
    kids
      .slice(1)
      .map((kid) => astTextWithBreaks(kid))
      .join(""),
  ).text;
  if (!tail.trim()) {
    return { n: match[1], label: match[2], reason: null, formulas: [] };
  }

  // The API emits a soft break and one `$...$` per line (the both-sides
  // equation, then the simplified equation). Anything else inline after the
  // bold heading stays ordinary Markdown.
  const parsed = lessonStepTail(tail);
  return parsed
    ? { n: match[1], label: match[2], reason: parsed.reason, formulas: parsed.formulas }
    : null;
}

/**
 * A move's reason on its heading line, however the writer set it off: "— rule" (the
 * server), "– rule", "- rule", ": rule" or "(rule)" (a model, November 2026). A hyphen
 * or en dash needs a space after it, so "-1" stays a number.
 */
const STEP_REASON_RE = /^[ \t]*(?:[—:][ \t]*([^\n]*)|[–-][ \t]+([^\n]*)|\(([^\n]*)\)[ \t]*(?=\n|$))/;

/** A formula alone: the step's first equation written on its heading line, not a reason. */
const LONE_FORMULA = /^\$[^$]+\$[.,;:]?$/;

function lessonStepTail(tail: string): { reason: string | null; formulas: string[] } | null {
  let rest = tail;
  let reason: string | null = null;
  // A reason sits on the heading line. A formula on that same line is ordinary
  // markdown (`**1. Result** $x^2$`); the working puts each equation on the next line.
  const reasonMatch = STEP_REASON_RE.exec(rest);
  if (reasonMatch) {
    reason = (reasonMatch[1] ?? reasonMatch[2] ?? reasonMatch[3] ?? "").trim() || null;
    if (reason && LONE_FORMULA.test(reason)) return null;
    rest = rest.slice(reasonMatch[0].length);
  }
  if (!/^\s*\n/.test(rest)) return null;
  const lines = rest
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) return null;
  const formulas: string[] = [];
  for (const line of lines) {
    const formula = /^\$([^$\n]+)\$$/.exec(line);
    if (!formula) return null;
    formulas.push(formula[1].trim());
  }
  return { reason, formulas };
}

/** A step's label, its maths typeset and the number it moves by in bold. */
export function lessonLabelNodes(
  label: string,
  keyPrefix: string,
  textStyle: StyleProp<TextStyle>,
  textColor: string,
): ReactNode {
  const operand = stepOperand(label);
  if (operand && !label.includes("$")) {
    return (
      <Text key={keyPrefix} style={textStyle} selectable>
        {operand.prefix}
        <Text style={Weight.bold}>{operand.operand}</Text>
        {operand.suffix}
      </Text>
    );
  }
  return splitInlineMath(label).map((part, i) =>
    part.type === "math" ? (
      <MathText
        scrollOverflow
        key={`${keyPrefix}-m-${i}`}
        latex={part.value}
        textColor={textColor}
        fontSize={mathSizeOf(textStyle)}
      />
    ) : (
      <Text key={`${keyPrefix}-t-${i}`} style={textStyle} selectable>
        {boldOperandText(part.value, operand)}
      </Text>
    ),
  );
}

function boldOperandText(
  value: string,
  operand: { prefix: string; operand: string; suffix: string } | null,
): ReactNode {
  if (!operand || operand.operand.includes("$") || !value.includes(operand.operand)) return value;
  const at = value.indexOf(operand.operand);
  return (
    <>
      {value.slice(0, at)}
      <Text style={Weight.bold}>{operand.operand}</Text>
      {value.slice(at + operand.operand.length)}
    </>
  );
}

/** The amount a both-sides move acts on, so "Subtract 4" can bold the 4. */
function stepOperand(label: string): { prefix: string; operand: string; suffix: string } | null {
  const subtract = /^(Subtract |Add )(.+?)( from both sides[\s\S]*| to both sides[\s\S]*)$/.exec(
    label,
  );
  if (subtract) return { prefix: subtract[1], operand: subtract[2], suffix: subtract[3] };
  const scale = /^(Divide both sides by |Multiply both sides by )(.+)$/.exec(label);
  if (scale) return { prefix: scale[1], operand: scale[2], suffix: "" };
  return null;
}

/** A step's reason, the rule under its move: smaller and dimmer than the working. */
function renderLessonReason(
  key: string,
  reason: string,
  styles: StyleMap,
  t: Theme,
): React.ReactElement {
  return (
    <View
      testID="lesson-step-reason"
      // The rule under the step: smaller and dimmer than the working.
      style={{
        flexDirection: "row",
        flexWrap: "wrap",
        alignItems: "baseline",
        marginBottom: Space.xxs,
      }}
    >
      {splitInlineMath(reason).map((part, i) =>
        part.type === "math" ? (
          <MathText
            scrollOverflow
            key={`${key}-reason-m-${i}`}
            latex={part.value}
            textColor={t.textTertiary}
            fontSize={Type.secondary.fontSize}
          />
        ) : (
          <Text
            key={`${key}-reason-t-${i}`}
            style={[styles.text, Type.secondary, { color: t.textTertiary }]}
            maxFontSizeMultiplier={DYNAMIC_TYPE_MAX}
            selectable
          >
            {part.value}
          </Text>
        ),
      )}
    </View>
  );
}

/** A lesson step: its number in a pill and the move, then the reason and each equation. */
export function renderLessonStep(
  key: string,
  step: { n: string; label: string; reason: string | null; formulas: string[] },
  styles: StyleMap,
  t: Theme,
): React.ReactElement {
  // A heading inside Solution, a level under the sections.
  const label = subheadingStyle(styles, t);
  return (
    // A numbered move is working inside Solution, with no rule (only Given and Required
    // have one); a little extra space above it so its lines read as one block.
    <View
      key={key}
      testID="lesson-step"
      style={[styles.paragraphRun, { marginTop: Space.xs }]}
    >
      <View
        style={{
          flexDirection: "row",
          alignItems: "flex-start",
          gap: STEP_BADGE.gap,
        }}
      >
        <StepBadge n={step.n} t={t} lineHeight={StyleSheet.flatten(label)?.lineHeight} />
        <View
          testID="lesson-step-label"
          style={{
            flex: 1,
            flexDirection: "row",
            flexWrap: "wrap",
            alignItems: "baseline",
          }}
        >
          {lessonLabelNodes(step.label, `${key}-label`, label, t.assistantText)}
        </View>
      </View>
      {step.reason || step.formulas.length ? (
        // The reason under the label it explains; the maths a step further in, as all working is.
        <View
          testID="lesson-step-formula"
          style={{ paddingLeft: STEP_LABEL_INSET, gap: Space.xxs }}
        >
          {step.reason ? renderLessonReason(key, step.reason, styles, t) : null}
          {step.formulas.map((formula, i) => (
            // A move's maths starts in the working column, as every line of a worked
            // solution does, a little apart from the words above it.
            <View
              key={`${key}-formula-${i}`}
              testID="lesson-step-maths"
              style={{
                alignItems: "flex-start",
                maxWidth: "100%",
                paddingLeft: WORK_INDENT - STEP_LABEL_INSET,
                marginTop: i === 0 ? WORK_GAP : 0,
              }}
            >
              <MathColumn inset={WORK_INDENT}>
                <MathText scrollOverflow latex={formula} fontSize={mathSizeOf(styles.body)} />
              </MathColumn>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}
