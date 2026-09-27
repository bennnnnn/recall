export type ArithmeticOperation =
  | "addition"
  | "subtraction"
  | "multiplication"
  | "division";

export type AdditionColumn = {
  position: number;
  place: string;
  addends: [number, number];
  carry_in: number;
  result_digit: number;
  carry_out: number;
};

export type SubtractionColumn = {
  position: number;
  place: string;
  top_digit: number;
  bottom_digit: number;
  working_top: number;
  result_digit: number;
  regrouped_from: string[];
};

export type PartialProduct = {
  position: number;
  place: string;
  multiplier_digit: number;
  unshifted_product: string;
  shifted_product: string;
  columns: MultiplicationColumn[];
};

export type MultiplicationColumn = {
  position: number;
  place: string;
  multiplicand_digit: number;
  carry_in: number;
  result_digit: number;
  carry_out: number;
};

export type DivisionStep = {
  index: number;
  column_end: number;
  partial_dividend: string;
  quotient_digit: number;
  product: string;
  remainder: string;
  bring_down?: number | null;
  next_partial?: string | null;
};

export type ArithmeticWorkSpec = {
  type: "arithmetic";
  operation: ArithmeticOperation;
  operator: "+" | "−" | "×" | "÷";
  expression: string;
  operands: [string, string];
  working_operands: [string, string];
  answer: string;
  decimal_places: number;
  addition_columns: AdditionColumn[];
  subtraction_columns: SubtractionColumn[];
  regrouped_minuend: string[];
  partial_products: PartialProduct[];
  quotient?: string | null;
  remainder?: string | null;
  division_steps: DivisionStep[];
  explanations: string[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function stringPair(value: unknown): value is [string, string] {
  return (
    Array.isArray(value) &&
    value.length === 2 &&
    value.every((item) => typeof item === "string")
  );
}

/** Parse server-owned procedure data. The client never derives the arithmetic. */
export function parseArithmeticWork(raw: string): ArithmeticWorkSpec | null {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isRecord(data) || data.type !== "arithmetic") return null;
  if (
    !["addition", "subtraction", "multiplication", "division"].includes(
      String(data.operation),
    ) ||
    !["+", "−", "×", "÷"].includes(String(data.operator)) ||
    typeof data.expression !== "string" ||
    !stringPair(data.operands) ||
    !stringPair(data.working_operands) ||
    typeof data.answer !== "string" ||
    typeof data.decimal_places !== "number" ||
    !Array.isArray(data.explanations) ||
    !data.explanations.every((item) => typeof item === "string")
  ) {
    return null;
  }
  const additionColumns = data.addition_columns;
  const subtractionColumns = data.subtraction_columns;
  const regroupedMinuend = data.regrouped_minuend;
  const partialProducts = data.partial_products;
  const divisionSteps = data.division_steps;
  if (
    !Array.isArray(additionColumns) ||
    !Array.isArray(subtractionColumns) ||
    !Array.isArray(regroupedMinuend) ||
    !Array.isArray(partialProducts) ||
    !Array.isArray(divisionSteps)
  ) {
    return null;
  }
  const trace = {
    addition:
      additionColumns.length > 0 &&
      additionColumns.every(
        (column) =>
          isRecord(column) &&
          typeof column.position === "number" &&
          typeof column.carry_out === "number",
      ),
    subtraction:
      subtractionColumns.length > 0 &&
      subtractionColumns.every(
        (column) =>
          isRecord(column) &&
          typeof column.position === "number" &&
          Array.isArray(column.regrouped_from),
      ),
    multiplication:
      partialProducts.length > 0 &&
      partialProducts.every(
        (product) =>
          isRecord(product) &&
          typeof product.shifted_product === "string" &&
          Array.isArray(product.columns),
      ),
    division:
      divisionSteps.length > 0 &&
      typeof data.quotient === "string" &&
      divisionSteps.every(
        (step) =>
          isRecord(step) &&
          typeof step.column_end === "number" &&
          typeof step.product === "string" &&
          typeof step.remainder === "string",
      ),
  } as const;
  if (!trace[data.operation as ArithmeticOperation]) return null;
  return data as ArithmeticWorkSpec;
}
