import { fireEvent, render } from "@testing-library/react-native";

import { RelatedPromptChips } from "@/features/suggestions/components/RelatedPromptChips";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

describe("RelatedPromptChips", () => {
  it("sends the full question string when a chip is pressed", async () => {
    const onSelect = jest.fn();
    const long =
      "what is the force on a 11 kg object accelerating at 3 m/s^2 from the top of a ramp";
    const { getByText } = await render(
      <RelatedPromptChips prompts={["what is 2+1?", long]} onSelect={onSelect} />,
    );
    fireEvent.press(getByText("what is 2+1?"));
    expect(onSelect).toHaveBeenCalledWith("what is 2+1?");
    fireEvent.press(getByText(/what is the force on a 11 kg/));
    expect(onSelect).toHaveBeenLastCalledWith(long);
  });
});
