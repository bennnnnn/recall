import { parseArithmeticWork } from "@/lib/math/arithmeticBlock";

function addition(overrides: Record<string, unknown> = {}) {
  return JSON.stringify({
    type: "arithmetic",
    operation: "addition",
    operator: "+",
    expression: "478 + 356",
    operands: ["478", "356"],
    working_operands: ["478", "356"],
    answer: "834",
    decimal_places: 0,
    addition_columns: [
      {
        position: 0,
        place: "ones",
        addends: [8, 6],
        carry_in: 0,
        result_digit: 4,
        carry_out: 1,
      },
    ],
    subtraction_columns: [],
    regrouped_minuend: [],
    partial_products: [],
    quotient: null,
    remainder: null,
    division_steps: [],
    explanations: ["Ones: 8 + 6 = 14. Write 4; carry 1."],
    ...overrides,
  });
}

describe("parseArithmeticWork", () => {
  it("accepts a complete server-owned trace", () => {
    const parsed = parseArithmeticWork(addition());

    expect(parsed?.answer).toBe("834");
    expect(parsed?.addition_columns[0]?.carry_out).toBe(1);
  });

  it("rejects malformed JSON and traces for the wrong operation", () => {
    expect(parseArithmeticWork("not json")).toBeNull();
    expect(
      parseArithmeticWork(
        addition({ operation: "division", quotient: null, division_steps: [] }),
      ),
    ).toBeNull();
  });

  it("rejects a spec without exactly two displayed operands", () => {
    expect(parseArithmeticWork(addition({ operands: ["478"] }))).toBeNull();
  });

  it("rejects division rows without server-owned alignment data", () => {
    expect(
      parseArithmeticWork(
        addition({
          operation: "division",
          operator: "÷",
          addition_columns: [],
          quotient: "2",
          division_steps: [{ product: "4", remainder: "0" }],
        }),
      ),
    ).toBeNull();
  });
});
