import { render } from "@testing-library/react-native";

import { MathDraftPreview } from "@/components/chat/MathDraftPreview";

describe("MathDraftPreview", () => {
  it("uses readable root degree text while preserving the full-size radicand", async () => {
    const { getByText, getByTestId } = await render(
      <MathDraftPreview input={String.raw`$\sqrt[6]{9}$`} showCaret={false} />,
    );
    expect(getByTestId("math-slot-nroot-index")).toBeOnTheScreen();
    expect(getByText("6")).toHaveStyle({ fontSize: 12, lineHeight: 15 });
    expect(getByText("9")).toHaveStyle({ fontSize: 16, lineHeight: 20 });
  });
});
