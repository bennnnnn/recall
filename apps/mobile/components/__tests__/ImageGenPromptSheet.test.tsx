import { fireEvent, render } from "@testing-library/react-native";

import { ImageGenPromptSheet } from "@/components/ImageGenPromptSheet";

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

describe("ImageGenPromptSheet", () => {
  it("pre-fills the prompt from initialPrompt, and submits the (possibly edited) trimmed text", async () => {
    const onSubmit = jest.fn();
    const { getByDisplayValue, getByText } = await render(
      <ImageGenPromptSheet
        visible
        generating={false}
        initialPrompt="a cat in a hat"
        onClose={jest.fn()}
        onSubmit={onSubmit}
      />,
    );

    const input = getByDisplayValue("a cat in a hat");
    await fireEvent.changeText(input, "a dog in a hat");
    await fireEvent.press(getByText("chat.image_gen_generate"));

    expect(onSubmit).toHaveBeenCalledWith("a dog in a hat");
  });

  it("starts blank when no initialPrompt is given (explicit button flow)", async () => {
    const onSubmit = jest.fn();
    const { getByPlaceholderText, getByText } = await render(
      <ImageGenPromptSheet
        visible
        generating={false}
        onClose={jest.fn()}
        onSubmit={onSubmit}
      />,
    );

    // Generate is disabled with nothing typed.
    await fireEvent.press(getByText("chat.image_gen_generate"));
    expect(onSubmit).not.toHaveBeenCalled();

    await fireEvent.changeText(getByPlaceholderText("chat.image_gen_placeholder"), "a sunset");
    await fireEvent.press(getByText("chat.image_gen_generate"));
    expect(onSubmit).toHaveBeenCalledWith("a sunset");
  });

  it("resets to empty (not the stale prompt) when re-opened without a new initialPrompt", async () => {
    const onSubmit = jest.fn();
    const { getByDisplayValue, queryByDisplayValue, rerender } = await render(
      <ImageGenPromptSheet
        visible
        generating={false}
        initialPrompt="a cat"
        onClose={jest.fn()}
        onSubmit={onSubmit}
      />,
    );
    expect(getByDisplayValue("a cat")).toBeOnTheScreen();

    await rerender(
      <ImageGenPromptSheet
        visible={false}
        generating={false}
        initialPrompt="a cat"
        onClose={jest.fn()}
        onSubmit={onSubmit}
      />,
    );
    await rerender(
      <ImageGenPromptSheet
        visible
        generating={false}
        onClose={jest.fn()}
        onSubmit={onSubmit}
      />,
    );

    expect(queryByDisplayValue("a cat")).toBeNull();
  });
});
