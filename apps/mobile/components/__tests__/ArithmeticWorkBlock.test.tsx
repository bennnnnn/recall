import { render } from "@testing-library/react-native";

import { ArithmeticWorkBlock } from "@/components/rich/ArithmeticWorkBlock";

const BASE = {
  type: "arithmetic",
  expression: "",
  decimal_places: 0,
  addition_columns: [],
  subtraction_columns: [],
  regrouped_minuend: [],
  partial_products: [],
  quotient: null,
  remainder: null,
  division_steps: [],
  explanations: ["Verified working."],
};

describe("ArithmeticWorkBlock", () => {
  it("renders aligned addition, its carry row, and the verified answer", async () => {
    const content = JSON.stringify({
      ...BASE,
      operation: "addition",
      operator: "+",
      expression: "478 + 356",
      operands: ["478", "356"],
      working_operands: ["478", "356"],
      answer: "834",
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
    });
    const { getByTestId, getByText } = await render(
      <ArithmeticWorkBlock content={content} />,
    );

    expect(getByTestId("arithmetic-annotation-row")).toBeOnTheScreen();
    expect(getByTestId("arithmetic-annotation-row").props.accessibilityLabel).toBe("1");
    expect(getByTestId("arithmetic-top-row")).toBeOnTheScreen();
    expect(getByTestId("arithmetic-bottom-row")).toBeOnTheScreen();
    expect(getByTestId("arithmetic-result-row")).toBeOnTheScreen();
    expect(getByText("Verified working.")).toBeOnTheScreen();
  });

  it("renders every row in a multi-addend sum", async () => {
    const content = JSON.stringify({
      ...BASE,
      operation: "addition",
      operator: "+",
      expression: "478 + 356 + 99",
      operands: ["478", "356", "99"],
      working_operands: ["478", "356", "99"],
      answer: "933",
      addition_columns: [
        {
          position: 0,
          place: "ones",
          addends: [8, 6, 9],
          carry_in: 0,
          result_digit: 3,
          carry_out: 2,
        },
      ],
    });
    const { getByTestId } = await render(<ArithmeticWorkBlock content={content} />);

    expect(getByTestId("arithmetic-top-row")).toBeOnTheScreen();
    expect(getByTestId("arithmetic-operand-row-1")).toBeOnTheScreen();
    expect(getByTestId("arithmetic-bottom-row")).toBeOnTheScreen();
  });

  it("renders long division in a dedicated bracket layout", async () => {
    const content = JSON.stringify({
      ...BASE,
      operation: "division",
      operator: "÷",
      expression: "437 / 6",
      operands: ["437", "6"],
      working_operands: ["437", "6"],
      answer: "72\\text{ remainder }5",
      quotient: "72",
      remainder: "5",
      division_steps: [
        {
          index: 0,
          column_end: 1,
          partial_dividend: "43",
          quotient_digit: 7,
          product: "42",
          remainder: "1",
          bring_down: 7,
          next_partial: "17",
        },
      ],
    });
    const { getByTestId, queryByText } = await render(
      <ArithmeticWorkBlock content={content} />,
    );

    expect(getByTestId("arithmetic-work-inline")).toBeOnTheScreen();
    expect(getByTestId("arithmetic-division-layout")).toBeOnTheScreen();
    expect(getByTestId("arithmetic-quotient").props.accessibilityLabel).toBe("72");
    expect(getByTestId("arithmetic-dividend").props.accessibilityLabel).toBe("437");
    expect(getByTestId("arithmetic-division-step-0")).toBeOnTheScreen();
    expect(
      getByTestId("arithmetic-division-product-0").props.accessibilityLabel,
    ).toBe("42");
    expect(queryByText("437 ÷ 6")).not.toBeOnTheScreen();
  });

  it("renders carries for every multiplication partial product", async () => {
    const content = JSON.stringify({
      ...BASE,
      operation: "multiplication",
      operator: "×",
      expression: "23 * 94",
      operands: ["23", "94"],
      working_operands: ["23", "94"],
      answer: "2162",
      partial_products: [
        {
          position: 0,
          place: "ones",
          multiplier_digit: 4,
          unshifted_product: "92",
          shifted_product: "92",
          columns: [
            {
              position: 0,
              place: "ones",
              multiplicand_digit: 3,
              carry_in: 0,
              result_digit: 2,
              carry_out: 1,
            },
            {
              position: 1,
              place: "tens",
              multiplicand_digit: 2,
              carry_in: 1,
              result_digit: 9,
              carry_out: 0,
            },
          ],
        },
        {
          position: 1,
          place: "tens",
          multiplier_digit: 9,
          unshifted_product: "207",
          shifted_product: "2070",
          columns: [
            {
              position: 0,
              place: "ones",
              multiplicand_digit: 3,
              carry_in: 0,
              result_digit: 7,
              carry_out: 2,
            },
            {
              position: 1,
              place: "tens",
              multiplicand_digit: 2,
              carry_in: 2,
              result_digit: 0,
              carry_out: 2,
            },
          ],
        },
      ],
    });
    const { getByTestId } = await render(<ArithmeticWorkBlock content={content} />);

    expect(getByTestId("arithmetic-multiplication-carries-0")).toBeOnTheScreen();
    expect(getByTestId("arithmetic-multiplication-carries-1")).toBeOnTheScreen();
    expect(
      getByTestId("arithmetic-multiplication-carries-1").props.accessibilityLabel,
    ).toBe("22");
    expect(getByTestId("arithmetic-result-row")).toBeOnTheScreen();
  });

  it("shows a leading carry when the answer gains a digit", async () => {
    const content = JSON.stringify({
      ...BASE,
      operation: "addition",
      operator: "+",
      expression: "9 + 1",
      operands: ["9", "1"],
      working_operands: ["9", "1"],
      answer: "10",
      addition_columns: [
        {
          position: 0,
          place: "ones",
          addends: [9, 1],
          carry_in: 0,
          result_digit: 0,
          carry_out: 1,
        },
      ],
    });
    const { getByTestId } = await render(<ArithmeticWorkBlock content={content} />);

    expect(getByTestId("arithmetic-annotation-row").props.accessibilityLabel).toBe("1");
  });

  it("allows very wide written arithmetic to scroll horizontally", async () => {
    const content = JSON.stringify({
      ...BASE,
      operation: "addition",
      operator: "+",
      expression: "999999999999999999999999 + 1",
      operands: ["999999999999999999999999", "1"],
      working_operands: ["999999999999999999999999", "1"],
      answer: "1000000000000000000000000",
      addition_columns: [
        {
          position: 0,
          place: "ones",
          addends: [9, 1],
          carry_in: 0,
          result_digit: 0,
          carry_out: 1,
        },
      ],
    });
    const { getByTestId } = await render(<ArithmeticWorkBlock content={content} />);

    expect(getByTestId("arithmetic-work-scroll").props.horizontal).toBe(true);
  });

  it("keeps placeholder zeros inside decimal long division", async () => {
    const content = JSON.stringify({
      ...BASE,
      operation: "division",
      operator: "÷",
      expression: "1.0 / 4",
      operands: ["1.0", "4"],
      working_operands: ["1.00", "4"],
      answer: "0.25",
      decimal_places: 2,
      quotient: "0.25",
      remainder: "0",
      division_steps: [
        {
          index: 0,
          column_end: 1,
          partial_dividend: "10",
          quotient_digit: 2,
          product: "8",
          remainder: "2",
          bring_down: 0,
          next_partial: "20",
        },
        {
          index: 1,
          column_end: 2,
          partial_dividend: "20",
          quotient_digit: 5,
          product: "20",
          remainder: "0",
          bring_down: null,
          next_partial: null,
        },
      ],
    });
    const { getByTestId } = await render(<ArithmeticWorkBlock content={content} />);

    expect(getByTestId("arithmetic-dividend").props.accessibilityLabel).toBe("1.00");
    expect(getByTestId("arithmetic-quotient").props.accessibilityLabel).toBe("0.25");
    expect(getByTestId("arithmetic-division-step-1")).toBeOnTheScreen();
  });

  it("renders nothing when the server trace is invalid", async () => {
    const { toJSON } = await render(<ArithmeticWorkBlock content="not json" />);
    expect(toJSON()).toBeNull();
  });

  it("renders typed fraction procedure steps without recalculating them", async () => {
    const content = JSON.stringify({
      type: "fraction",
      operation: "add",
      operands: ["1/2", "1/3"],
      answer: "\\frac{5}{6}",
      exact_numerator: 5,
      exact_denominator: 6,
      steps: [
        {
          kind: "common_denominator",
          explanation: "Use the least common denominator 6.",
          expression: "\\frac{3}{6}+\\frac{2}{6}",
          result: "\\frac{5}{6}",
        },
      ],
    });
    const { getByTestId, getByText } = await render(
      <ArithmeticWorkBlock content={content} />,
    );

    expect(getByTestId("fraction-step-0")).toBeOnTheScreen();
    expect(getByText("1. Use the least common denominator 6.")).toBeOnTheScreen();
  });

  it("renders a unary improper-to-mixed procedure", async () => {
    const content = JSON.stringify({
      type: "fraction",
      operation: "improper_to_mixed",
      operands: ["29/4"],
      answer: "7\\frac{1}{4}",
      exact_numerator: 29,
      exact_denominator: 4,
      steps: [
        {
          kind: "convert",
          explanation: "4 goes into 29 exactly 7 whole times, with 1 left over.",
          expression: "29",
          result: "4\\times 7+1",
        },
        {
          kind: "convert",
          explanation:
            "Keep the quotient as the whole number and put the remainder over the original denominator.",
          expression: "\\frac{29}{4}",
          result: "7+\\frac{1}{4}",
        },
      ],
    });
    const { getByTestId, getByText, queryByText } = await render(
      <ArithmeticWorkBlock content={content} />,
    );

    expect(getByTestId("fraction-work-inline")).toBeOnTheScreen();
    expect(getByTestId("fraction-step-0")).toBeOnTheScreen();
    expect(getByTestId("fraction-step-1")).toBeOnTheScreen();
    expect(
      getByText("1. 4 goes into 29 exactly 7 whole times, with 1 left over."),
    ).toBeOnTheScreen();
    expect(queryByText("29/4")).not.toBeOnTheScreen();
  });
});
