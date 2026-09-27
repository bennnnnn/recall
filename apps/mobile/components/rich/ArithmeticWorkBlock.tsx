import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { CardShell } from "@/components/rich/CardShell";
import { StepList } from "@/components/rich/StepList";
import { MATH_FONT } from "@/lib/fonts";
import { parseArithmeticWork } from "@/lib/math/arithmeticBlock";
import type { ArithmeticWorkSpec } from "@/lib/math/arithmeticBlock";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

const CELL_WIDTH = 25;
const DOT_WIDTH = 12;

function cells(value: string, width: number): string[] {
  return value.padStart(width, " ").split("");
}

function DigitRow({
  value,
  width,
  operator,
  muted = false,
  testID,
}: {
  value: string;
  width: number;
  operator?: string;
  muted?: boolean;
  testID?: string;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <View style={s.digitRow} testID={testID} accessibilityLabel={value.trim()}>
      <Text style={[s.operator, muted && s.muted]}>{operator ?? " "}</Text>
      <DigitCells value={value} width={width} muted={muted} />
    </View>
  );
}

function DigitCells({
  value,
  width,
  muted = false,
  testID,
}: {
  value: string;
  width: number;
  muted?: boolean;
  testID?: string;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <View style={s.digitRow} testID={testID} accessibilityLabel={value.trim()}>
      {cells(value, width).map((char, index) => (
        <Text
          key={`${index}-${char}`}
          style={[s.digit, char === "." && s.dot, muted && s.muted]}
        >
          {char}
        </Text>
      ))}
    </View>
  );
}

function annotationRow(
  template: string,
  width: number,
  annotations: Map<number, string>,
): { label: string; dot: boolean }[] {
  const padded = cells(template, width);
  const digitIndexes = padded
    .map((char, index) => (char >= "0" && char <= "9" ? index : -1))
    .filter((index) => index >= 0)
    .reverse();
  return padded.map((char, index) => {
    const position = digitIndexes.indexOf(index);
    const label = position >= 0 ? annotations.get(position) ?? " " : char === "." ? "." : " ";
    return { label, dot: char === "." };
  });
}

function AnnotationRow({
  spec,
  width,
}: {
  spec: ArithmeticWorkSpec;
  width: number;
}) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const annotations = new Map<number, string>();
  if (spec.operation === "addition") {
    spec.addition_columns.forEach((column) => {
      if (column.carry_out) annotations.set(column.position + 1, String(column.carry_out));
    });
  } else {
    const didRegroup = spec.subtraction_columns.some(
      (column) => column.regrouped_from.length > 0,
    );
    if (!didRegroup) return null;
    [...spec.regrouped_minuend].reverse().forEach((value, position) => {
      annotations.set(position, value);
    });
  }
  const row = annotationRow(spec.working_operands[0], width, annotations);
  return (
    <View style={s.digitRow} testID="arithmetic-annotation-row">
      <Text style={s.operator}> </Text>
      {row.map(({ label, dot }, index) => (
        <Text key={index} style={[s.annotation, dot && s.dot]}>
          {label}
        </Text>
      ))}
    </View>
  );
}

function ColumnWork({ spec }: { spec: ArithmeticWorkSpec }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const width = Math.max(
    spec.answer.length,
    ...spec.working_operands.map((value) => value.length),
  );
  return (
    <View style={s.work}>
      <AnnotationRow spec={spec} width={width} />
      <DigitRow value={spec.working_operands[0]} width={width} testID="arithmetic-top-row" />
      <DigitRow
        value={spec.working_operands[1]}
        width={width}
        operator={spec.operator}
        testID="arithmetic-bottom-row"
      />
      <View style={[s.rule, { width: width * CELL_WIDTH + CELL_WIDTH }]} />
      <DigitRow value={spec.answer} width={width} testID="arithmetic-result-row" />
    </View>
  );
}

function MultiplicationWork({ spec }: { spec: ArithmeticWorkSpec }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const rows = spec.partial_products.map((product) => product.shifted_product);
  const width = Math.max(
    spec.answer.length,
    ...spec.working_operands.map((value) => value.length),
    ...rows.map((value) => value.length),
  );
  const annotations = new Map<number, string>();
  spec.partial_products[0]?.columns.forEach((column) => {
    if (column.carry_out) {
      annotations.set(column.position + 1, String(column.carry_out));
    }
  });
  const carryRow = annotationRow(spec.working_operands[0], width, annotations);
  return (
    <View style={s.work}>
      {annotations.size ? (
        <View style={s.digitRow} testID="arithmetic-multiplication-carries">
          <Text style={s.operator}> </Text>
          {carryRow.map(({ label, dot }, index) => (
            <Text key={index} style={[s.annotation, dot && s.dot]}>
              {label}
            </Text>
          ))}
        </View>
      ) : null}
      <DigitRow value={spec.working_operands[0]} width={width} />
      <DigitRow value={spec.working_operands[1]} width={width} operator="×" />
      <View style={[s.rule, { width: width * CELL_WIDTH + CELL_WIDTH }]} />
      {rows.map((row, index) => (
        <DigitRow
          key={`${index}-${row}`}
          value={row}
          width={width}
          muted={rows.length > 1}
        />
      ))}
      {rows.length > 1 ? (
        <View style={[s.rule, { width: width * CELL_WIDTH + CELL_WIDTH }]} />
      ) : null}
      <DigitRow value={spec.answer} width={width} testID="arithmetic-result-row" />
    </View>
  );
}

function displayColumnEnd(dividend: string, digitColumnEnd: number): number {
  const decimalIndex = dividend.indexOf(".");
  if (decimalIndex >= 0 && digitColumnEnd >= decimalIndex) return digitColumnEnd + 1;
  return digitColumnEnd;
}

function positionedValue(value: string, end: number, width: number): string {
  const row = Array.from({ length: width }, () => " ");
  const start = Math.max(0, end - value.length + 1);
  value.split("").forEach((char, index) => {
    if (start + index < row.length) row[start + index] = char;
  });
  return row.join("");
}

function DivisionWork({ spec }: { spec: ArithmeticWorkSpec }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [dividend, divisor] = spec.working_operands;
  const width = dividend.length;
  return (
    <View style={s.divisionWork} testID="arithmetic-division-layout">
      <View style={s.quotientRow}>
        <Text style={s.divisorSpacer}>{divisor}</Text>
        <DigitCells
          value={spec.quotient ?? ""}
          width={width}
          testID="arithmetic-quotient"
        />
      </View>
      <View style={s.dividendRow}>
        <Text style={s.divisor}>{divisor}</Text>
        <View style={s.dividendBracket}>
          <DigitCells value={dividend} width={width} testID="arithmetic-dividend" />
        </View>
      </View>
      <View style={s.divisionSteps}>
        <View style={s.divisorSpacer} />
        <View style={s.divisionStepDigits}>
          {spec.division_steps.map((step) => {
            const productEnd = displayColumnEnd(dividend, step.column_end);
            const nextEnd = displayColumnEnd(
              dividend,
              step.column_end + (step.bring_down == null ? 0 : 1),
            );
            const nextValue = step.next_partial ?? step.remainder;
            const ruleDigits = Math.max(
              step.partial_dividend.length,
              step.product.length,
            );
            const trailing = Math.max(0, width - productEnd - 1);
            return (
              <View key={step.index} testID={`arithmetic-division-step-${step.index}`}>
                <DigitRow
                  value={positionedValue(step.product, productEnd, width)}
                  width={width}
                  operator="−"
                  muted
                  testID={`arithmetic-division-product-${step.index}`}
                />
                <View
                  style={[
                    s.divisionRule,
                    {
                      width: ruleDigits * CELL_WIDTH,
                      marginRight: trailing * CELL_WIDTH,
                    },
                  ]}
                />
                <DigitRow
                  value={positionedValue(nextValue, nextEnd, width)}
                  width={width}
                />
              </View>
            );
          })}
        </View>
      </View>
    </View>
  );
}

export function ArithmeticWorkBlock({ content }: { content: string }) {
  const spec = parseArithmeticWork(content);
  if (!spec) return null;
  const layout =
    spec.operation === "addition" || spec.operation === "subtraction" ? (
      <ColumnWork spec={spec} />
    ) : spec.operation === "multiplication" ? (
      <MultiplicationWork spec={spec} />
    ) : (
      <DivisionWork spec={spec} />
    );
  const label = `${spec.operands[0]} ${spec.operator} ${spec.operands[1]}`;
  return (
    <CardShell label={label} copyText={`${label} = ${spec.answer}`} accent={false}>
      {layout}
      <View style={styles.steps}>
        <StepList steps={spec.explanations} />
      </View>
    </CardShell>
  );
}

const styles = StyleSheet.create({ steps: { marginTop: Space.sm } });

function makeStyles(t: Theme) {
  return StyleSheet.create({
    work: { alignSelf: "center", alignItems: "flex-end", paddingVertical: Space.xs },
    digitRow: { flexDirection: "row", alignItems: "flex-end" },
    operator: {
      ...Type.h1,
      width: CELL_WIDTH,
      fontFamily: MATH_FONT,
      color: t.text,
      textAlign: "center",
    },
    digit: {
      ...Type.h1,
      width: CELL_WIDTH,
      fontFamily: MATH_FONT,
      lineHeight: 30,
      color: t.text,
      textAlign: "center",
      fontVariant: ["tabular-nums"],
    },
    dot: { width: DOT_WIDTH },
    annotation: {
      ...Type.secondary,
      width: CELL_WIDTH,
      fontFamily: MATH_FONT,
      lineHeight: 19,
      color: t.primary,
      textAlign: "center",
    },
    muted: { color: t.textSecondary },
    rule: {
      height: StyleSheet.hairlineWidth,
      backgroundColor: t.text,
      marginVertical: Space.xxs,
    },
    divisionWork: { alignSelf: "center", paddingVertical: Space.sm },
    quotientRow: { flexDirection: "row", alignItems: "flex-end" },
    divisorSpacer: {
      ...Type.h1,
      minWidth: 52,
      opacity: 0,
      fontFamily: MATH_FONT,
      paddingHorizontal: Space.xs,
    },
    dividendRow: { flexDirection: "row", alignItems: "flex-start" },
    divisor: {
      ...Type.h1,
      minWidth: 52,
      fontFamily: MATH_FONT,
      lineHeight: 34,
      color: t.text,
      textAlign: "right",
      paddingRight: Space.xs,
    },
    dividendBracket: {
      borderLeftWidth: 1.5,
      borderTopWidth: 1.5,
      borderColor: t.text,
      paddingHorizontal: Space.xs,
      paddingTop: 2,
      minWidth: 80,
    },
    divisionSteps: { flexDirection: "row", alignItems: "flex-start" },
    divisionStepDigits: { alignItems: "flex-end", paddingHorizontal: Space.xs },
    divisionRule: { height: StyleSheet.hairlineWidth, backgroundColor: t.text },
  });
}
