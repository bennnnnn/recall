import { render } from "@testing-library/react-native";

import { MathDraftPreview } from "@/components/chat/MathDraftPreview";
import { lightTheme } from "@/lib/theme";

describe("MathDraftPreview", () => {
  it("uses readable root degree text while preserving the full-size radicand", async () => {
    const { getByText, getByTestId } = await render(
      <MathDraftPreview input={String.raw`$\sqrt[6]{9}$`} showCaret={false} />,
    );
    expect(getByTestId("math-slot-nroot-index")).toBeOnTheScreen();
    expect(getByText("6")).toHaveStyle({ fontSize: 12, lineHeight: 15 });
    expect(getByText("9")).toHaveStyle({ fontSize: 16, lineHeight: 20 });
  });

  it("paints a dropped command slash as a fraction", async () => {
    const { getByTestId, queryByText } = await render(
      <MathDraftPreview input="$frac{d^{2}}{dx^{2}}$" showCaret={false} />,
    );
    expect(getByTestId("math-frac")).toBeOnTheScreen();
    expect(queryByText(/frac\{/)).toBeNull();
  });

  it("highlights only an empty slot", async () => {
    const empty = await render(<MathDraftPreview input={String.raw`$\frac{}{}$`} caret={7} />);
    expect(empty.getByTestId("math-slot-num")).toHaveStyle({
      backgroundColor: lightTheme.primaryLight,
    });
    expect(empty.getByTestId("math-slot-den")).toHaveStyle({
      backgroundColor: lightTheme.primaryLight,
    });
    expect(empty.getByTestId("math-slot-den-placeholder")).not.toHaveStyle({
      borderBottomWidth: 1,
    });

    const symbol = await render(<MathDraftPreview input="$y$" caret={2} />);
    expect(symbol.getByTestId("math-slot-text")).not.toHaveStyle({
      backgroundColor: lightTheme.primaryLight,
    });

    const filled = await render(<MathDraftPreview input={String.raw`$\frac{8}{}$`} caret={8} />);
    expect(filled.getByTestId("math-slot-num")).not.toHaveStyle({
      backgroundColor: lightTheme.primaryLight,
    });
    expect(filled.getByTestId("math-slot-den")).toHaveStyle({
      backgroundColor: lightTheme.primaryLight,
    });
  });

  it("draws a definite integral with a lower limit and an upper limit", async () => {
    const { getByTestId } = await render(
      <MathDraftPreview input={String.raw`$\int_{}^{}$`} showCaret={false} />,
    );
    expect(getByTestId("math-integral-sign")).toHaveStyle({ fontSize: 32, lineHeight: 36 });
    expect(getByTestId("math-integral-limits")).toHaveStyle({ marginLeft: 4 });
    expect(getByTestId("math-slot-sub")).toHaveStyle({
      backgroundColor: lightTheme.primaryLight,
    });
    expect(getByTestId("math-slot-sup")).toHaveStyle({
      backgroundColor: lightTheme.primaryLight,
    });
  });
});
