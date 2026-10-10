import { fireEvent, render } from "@testing-library/react-native";

import { RelatedPromptLines } from "@/features/suggestions/components/RelatedPromptLines";

const PHYSICS =
  "Why is the force the product of mass and acceleration for this object?";
const MATH =
  "Why does the equation X^2 = 9 have two solutions, +3 and -3, instead of just one?";

describe("RelatedPromptLines", () => {
  it("sends the full question when the line is pressed", async () => {
    const onSelect = jest.fn();
    const { getByLabelText, getAllByRole, getAllByTestId, queryByText } = await render(
      <RelatedPromptLines prompts={[MATH, PHYSICS]} onSelect={onSelect} />,
    );

    expect(queryByText("chat.suggestions")).toBeNull();
    expect(queryByText("X^2 = 9")).toBeNull();
    expect(getAllByRole("button")).toHaveLength(2);
    expect(getAllByTestId("related-prompt-divider")).toHaveLength(1);

    fireEvent.press(getByLabelText(MATH));
    expect(onSelect).toHaveBeenCalledWith(MATH);
    fireEvent.press(getByLabelText(PHYSICS));
    expect(onSelect).toHaveBeenLastCalledWith(PHYSICS);
  });
});
