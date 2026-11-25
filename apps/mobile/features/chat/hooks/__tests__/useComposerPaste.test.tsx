import { act, renderHook } from "@testing-library/react-native";

import { useComposerPaste } from "@/features/chat/hooks/useComposerPaste";
import { PASTE_ATTACH_MIN_CHARS } from "@/features/chat/model/composerPaste";

const mockError = jest.fn();
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => ({ error: mockError }) }));

const long = "p".repeat(PASTE_ATTACH_MIN_CHARS + 1);

async function setup(input: string, options: { hasAttachment?: boolean; written?: boolean } = {}) {
  const onPasteAsFile = jest.fn((_text: string) => options.written ?? true);
  const onChangeText = jest.fn();
  const insertText = jest.fn();
  const { result } = await renderHook(() =>
    useComposerPaste({
      input,
      onPasteAsFile,
      hasAttachment: options.hasAttachment ?? false,
      field: { onChangeText, pasteText: insertText },
    }),
  );
  return { result, onPasteAsFile, onChangeText, insertText };
}

beforeEach(() => jest.clearAllMocks());

describe("the composer's long pastes", () => {
  it("passes typing and a short paste through to the field", async () => {
    const { result, onPasteAsFile, onChangeText } = await setup("Hi");
    await act(() => result.current.onFieldChange("Hi!"));
    await act(() => result.current.onFieldChange(`Hi${"q".repeat(PASTE_ATTACH_MIN_CHARS)}`));
    expect(onChangeText).toHaveBeenNthCalledWith(1, "Hi!");
    expect(onChangeText).toHaveBeenCalledTimes(2);
    expect(onPasteAsFile).not.toHaveBeenCalled();
  });

  it("turns a long paste into the attachment and leaves the draft as it was", async () => {
    const { result, onPasteAsFile, onChangeText } = await setup("Summarize: ");
    await act(() => result.current.onFieldChange(`Summarize: ${long}`));
    expect(onPasteAsFile).toHaveBeenCalledWith(long);
    // The field holds the draft still: the controlled input puts it back by itself.
    expect(onChangeText).not.toHaveBeenCalled();
  });

  it("takes out the selection a long paste replaced", async () => {
    const { result, onChangeText } = await setup("keep OLD end");
    await act(() => result.current.onFieldChange(`keep Q${long} end`));
    expect(onChangeText).toHaveBeenCalledWith("keep  end");
  });

  it("refuses a paste past the limit with a message, and adds nothing", async () => {
    const { result, onPasteAsFile, onChangeText } = await setup("draft");
    await act(() => result.current.onFieldChange(`draft${"x".repeat(200_001)}`));
    expect(mockError).toHaveBeenCalledWith("chat.paste_too_long");
    expect(onPasteAsFile).not.toHaveBeenCalled();
    expect(onChangeText).not.toHaveBeenCalled();
  });

  it("keeps a long paste as text while another file is attached, and still refuses one too long", async () => {
    const { result, onPasteAsFile, onChangeText } = await setup("", { hasAttachment: true });
    await act(() => result.current.onFieldChange(long));
    expect(onPasteAsFile).not.toHaveBeenCalled();
    expect(onChangeText).toHaveBeenCalledWith(long);
    await act(() => result.current.onFieldChange("x".repeat(200_001)));
    expect(mockError).toHaveBeenCalledWith("chat.paste_too_long");
  });

  it("keeps the paste as text when its file cannot be written", async () => {
    const { result, onChangeText } = await setup("", { written: false });
    await act(() => result.current.onFieldChange(long));
    expect(onChangeText).toHaveBeenCalledWith(long);
  });

  it("reads the maths pad's Paste key the same way", async () => {
    const { result, onPasteAsFile, insertText } = await setup("x");
    await act(() => result.current.onPadPaste("x^2"));
    expect(insertText).toHaveBeenCalledWith("x^2");
    await act(() => result.current.onPadPaste(long));
    expect(onPasteAsFile).toHaveBeenCalledWith(long);
    expect(insertText).toHaveBeenCalledTimes(1);
  });
});

it("says a refusal in the chat's banner when the composer has one", async () => {
  const onNotice = jest.fn();
  const { result } = await renderHook(() =>
    useComposerPaste({
      input: "",
      onPasteAsFile: () => true,
      onNotice,
      hasAttachment: false,
      field: { onChangeText: jest.fn(), pasteText: jest.fn() },
    }),
  );
  await act(() => result.current.onFieldChange("x".repeat(200_001)));
  expect(onNotice).toHaveBeenCalledWith("chat.paste_too_long", "alert-circle", "error");
  expect(mockError).not.toHaveBeenCalled();
});

it("tells when the draft is longer than a message may be", async () => {
  const field = { onChangeText: jest.fn(), pasteText: jest.fn() };
  const { result, rerender } = await renderHook(
    ({ input }: { input: string }) => useComposerPaste({ input, hasAttachment: false, field }),
    { initialProps: { input: "a".repeat(32_000) } },
  );
  expect(result.current.tooLong).toBe(false);
  await rerender({ input: "a".repeat(32_001) });
  expect(result.current.tooLong).toBe(true);
});
