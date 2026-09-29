import { fireEvent, render } from "@testing-library/react-native";

import { SuggestionChips } from "@/features/suggestions/components/SuggestionChips";
import type { Suggestion } from "@/lib/api";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

function item(id: string, text: string): Suggestion {
  return {
    id,
    text,
    category: "followup",
    source: "chat",
    created_at: "2026-01-01T00:00:00.000Z",
  };
}

describe("SuggestionChips", () => {
  it("renders nothing when there are no suggestions", async () => {
    const { queryByText } = await render(
      <SuggestionChips suggestions={[]} onSelect={jest.fn()} onDismiss={jest.fn()} />,
    );
    expect(queryByText("chat.suggestions")).toBeNull();
  });

  it("selects the full prompt and dismisses on a long press", async () => {
    const onSelect = jest.fn();
    const onDismiss = jest.fn();
    const long = "Ask about the history of the number line and how it is taught";
    const { getByText } = await render(
      <SuggestionChips
        suggestions={[item("1", "Review fractions"), item("2", long)]}
        onSelect={onSelect}
        onDismiss={onDismiss}
      />,
    );
    fireEvent.press(getByText("Review fractions"));
    expect(onSelect).toHaveBeenCalledWith("Review fractions");
    fireEvent(getByText(/Ask about the history/), "longPress");
    expect(onDismiss).toHaveBeenCalledWith("2");
  });
});
