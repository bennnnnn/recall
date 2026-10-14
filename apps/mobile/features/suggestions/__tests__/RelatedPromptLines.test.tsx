import { act, cleanup, fireEvent, render } from "@testing-library/react-native";

import { RelatedPromptLines } from "@/features/suggestions/components/RelatedPromptLines";

const PHYSICS =
  "Why is the force the product of mass and acceleration for this object?";
const MATH =
  "Why does the equation X^2 = 9 have two solutions, +3 and -3, instead of just one?";

describe("RelatedPromptLines", () => {
  afterEach(() => {
    cleanup();
  });

  it("sends the full question when the line is pressed", async () => {
    const onSelect = jest.fn();
    const { getByLabelText, getAllByRole, getAllByTestId, queryByText } = await render(
      <RelatedPromptLines prompts={[MATH, PHYSICS]} onSelect={onSelect} />,
    );

    expect(queryByText("X^2 = 9")).toBeNull();
    expect(getAllByRole("button")).toHaveLength(2);
    // A rule opens every row, the first one included.
    expect(getAllByTestId("related-prompt-divider")).toHaveLength(2);

    await act(async () => {
      fireEvent.press(getByLabelText(MATH));
    });
    expect(onSelect).toHaveBeenCalledWith(MATH);
    await act(async () => {
      fireEvent.press(getByLabelText(PHYSICS));
    });
    expect(onSelect).toHaveBeenLastCalledWith(PHYSICS);
  });

  it("does not offer a fragment or a glued equation", async () => {
    const onSelect = jest.fn();
    const { queryByLabelText, getByLabelText } = await render(
      <RelatedPromptLines
        prompts={["How", "Education level", String.raw`Why does $^5\sqrt{x}=0^5$ equal zero?`, MATH]}
        onSelect={onSelect}
      />,
    );

    expect(queryByLabelText("How")).toBeNull();
    expect(queryByLabelText("Education level")).toBeNull();
    fireEvent.press(getByLabelText(MATH));
    expect(onSelect).toHaveBeenCalledWith(MATH);
  });
});
