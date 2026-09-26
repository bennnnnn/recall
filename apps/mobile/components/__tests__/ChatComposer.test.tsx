import { useState } from "react";
import { StyleSheet } from "react-native";
import * as Clipboard from "expo-clipboard";
import { act, fireEvent, render, waitFor } from "@testing-library/react-native";

import { ChatComposer } from "@/components/chat/ChatComposer";
import { ComposerDraftProvider, useComposerDraftApi } from "@/contexts/ComposerDraftContext";

jest.mock("@/contexts/AuthContext", () => ({
  useAuthToken: () => "t",
}));

jest.mock("expo-clipboard", () => ({
  setStringAsync: jest.fn(),
  getStringAsync: jest.fn(async () => ""),
  hasImageAsync: jest.fn(async () => false),
  getImageAsync: jest.fn(),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

jest.mock("expo-haptics", () => ({
  selectionAsync: jest.fn(async () => undefined),
  impactAsync: jest.fn(async () => undefined),
  notificationAsync: jest.fn(async () => undefined),
  ImpactFeedbackStyle: { Light: "light" },
  NotificationFeedbackType: { Success: "success", Warning: "warning" },
}));

jest.mock("@/features/speech/components/VoiceComposerWaveform", () => ({
  VoiceComposerWaveform: () => null,
}));

jest.mock("@/features/speech/components/VoiceMicButton", () => ({
  VoiceMicButton: () => null,
}));

jest.mock("@/features/speech/components/LiveTalkButton", () => {
  const { Pressable } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    LiveTalkButton: ({ onPress }: { onPress: () => void }) => (
      <Pressable testID="live-talk-button" onPress={onPress} />
    ),
  };
});

jest.mock("@/features/attachments/components/ComposerAttachmentPreview", () => ({
  ComposerAttachmentPreview: () => null,
}));

const baseProps = {
  visible: true,
  input: "",
  onChangeInput: jest.fn(),
  streaming: false,
  attachBusy: false,
  pendingAttachment: null,
  onRemoveAttachment: jest.fn(),
  onCloseAttachSheet: jest.fn(),
  onPickAttachment: jest.fn(),
  onSend: jest.fn(),
  onStop: jest.fn(),
  isOffline: false,
  mathContext: true,
};

describe("ChatComposer math keyboard", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it.each([
    "What is sqrt{81}?",
    "Let x=-5. Evaluate x^2",
    "Use $x^2$ with a $5 example",
  ])("keeps ordinary typing on the messaging keyboard with the native caret: %s", async (text) => {
    function Harness() {
      const [input, setInput] = useState("");
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId, queryByTestId } = await render(<Harness />);
    for (let i = 1; i <= text.length; i += 1) {
      const next = text.slice(0, i);
      await fireEvent.changeText(getByTestId("chat-composer-input"), next);
      const native = getByTestId("chat-composer-input");
      expect(native.props.value).toBe(next);
      expect(native.props.autoCorrect).toBe(true);
      expect(native.props.spellCheck).toBe(true);
      expect(native.props.autoCapitalize).toBe("sentences");
      expect(native.props.selection).toBeUndefined();
      expect(native.props.caretHidden).toBe(false);
      expect(native.props.pointerEvents).toBe("auto");
      expect(queryByTestId("math-draft-preview")).toBeNull();
    }
  });

  it("uses messaging input until the math pad is open", async () => {
    const { getByTestId } = await render(<ChatComposer {...baseProps} />);
    const expectMessaging = () => {
      const native = getByTestId("chat-composer-input");
      expect(native.props.autoCorrect).toBe(true);
      expect(native.props.spellCheck).toBe(true);
      expect(native.props.autoCapitalize).toBe("sentences");
    };
    const expectMathEditor = () => {
      const native = getByTestId("chat-composer-input");
      expect(native.props.autoCorrect).toBe(false);
      expect(native.props.spellCheck).toBe(false);
      expect(native.props.autoCapitalize).toBe("none");
    };
    expectMessaging();
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    expectMathEditor();
    await fireEvent.press(getByTestId("math-keyboard-abc"));
    expectMessaging();
  });

  it("does not enable preview just by opening and closing an empty math pad", async () => {
    function Harness() {
      const [input, setInput] = useState("");
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId, queryByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-keyboard-abc"));
    const text = "The price is $5.00";
    for (let i = 1; i <= text.length; i += 1) {
      await fireEvent.changeText(getByTestId("chat-composer-input"), text.slice(0, i));
      expect(getByTestId("chat-composer-input").props.selection).toBeUndefined();
      expect(queryByTestId("math-draft-preview")).toBeNull();
    }
  });

  it("keeps a saved native draft literal after switching away from a math draft", async () => {
    let api: ReturnType<typeof useComposerDraftApi>;
    function ApiProbe() {
      api = useComposerDraftApi();
      return null;
    }
    const { getByTestId, queryByTestId } = await render(
      <ComposerDraftProvider>
        <ApiProbe />
        <ChatComposer {...baseProps} input={undefined} onChangeInput={undefined} />
      </ComposerDraftProvider>,
    );
    await act(() => api.switchThread("literal"));
    await fireEvent.changeText(getByTestId("chat-composer-input"), "The price is $5");
    await act(() => api.switchThread("math"));
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-key-frac"));
    expect(getByTestId("math-draft-preview")).toBeTruthy();
    await act(() => api.switchThread("literal"));
    expect(getByTestId("chat-composer-input").props.value).toBe("The price is $5");
    expect(getByTestId("chat-composer-input").props.selection).toBeUndefined();
    expect(queryByTestId("math-draft-preview")).toBeNull();
    expect(queryByTestId("math-keyboard-pad")).toBeNull();
    await fireEvent.changeText(getByTestId("chat-composer-input"), "The price is $50");
    expect(getByTestId("chat-composer-input").props.value).toBe("The price is $50");
    expect(queryByTestId("math-draft-preview")).toBeNull();
  });

  it("shows a guarded busy send control before streaming starts", async () => {
    const onSend = jest.fn();
    const { getByLabelText } = await render(
      <ChatComposer {...baseProps} input="" sendBusy onSend={onSend} />,
    );

    const send = getByLabelText("chat.sending");
    expect(send.props.accessibilityState).toEqual({ disabled: true, busy: true });
    await fireEvent.press(send);
    expect(onSend).not.toHaveBeenCalled();
  });

  it("shows an immediate locating status without clearing the draft", async () => {
    const { getByTestId } = await render(
      <ChatComposer
        {...baseProps}
        input="coffee near me"
        sendBusy
        sendStatus="chat.locating"
      />,
    );

    expect(getByTestId("chat-composer-input").props.value).toBe("coffee near me");
    expect(getByTestId("composer-send-status").props.children).toBe(
      "chat.locating",
    );
  });

  it("returns an expanded multiline input to its default height after send", async () => {
    function Harness() {
      const [input, setInput] = useState(
        "A long message that wraps across several lines in the composer before it is sent.",
      );
      return (
        <ChatComposer
          {...baseProps}
          input={input}
          onChangeInput={setInput}
          onSend={() => setInput("")}
        />
      );
    }

    const { getByTestId, getByLabelText } = await render(<Harness />);
    const composerInput = getByTestId("chat-composer-input");

    await fireEvent(composerInput, "contentSizeChange", {
      nativeEvent: { contentSize: { width: 240, height: 112 } },
    });
    expect(getByTestId("chat-composer-input")).toHaveStyle({ height: 112 });

    await fireEvent.press(getByLabelText("chat.send_a11y"));

    await waitFor(() => {
      expect(getByTestId("chat-composer-input").props.value).toBe("");
      expect(getByTestId("chat-composer-input")).toHaveStyle({ height: 44 });
    });
  });

  it("grows the field when a leading Return adds a line", async () => {
    function Harness() {
      const [input, setInput] = useState("");
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }

    const { getByTestId } = await render(<Harness />);
    const composerInput = getByTestId("chat-composer-input");

    expect(getByTestId("composer-input-row")).toHaveStyle({ alignItems: "center" });
    expect(composerInput.props.placeholder).toBe("chat.placeholder");

    await fireEvent.changeText(composerInput, "\n");
    await fireEvent(composerInput, "contentSizeChange", {
      nativeEvent: { contentSize: { width: 240, height: 50 } },
    });

    expect(getByTestId("chat-composer-input").props.value).toBe("\n");
    expect(getByTestId("chat-composer-input").props.placeholder).toBe("chat.placeholder");
    expect(getByTestId("chat-composer-input")).toHaveStyle({ height: 68 });
    expect(getByTestId("composer-input-row")).toHaveStyle({ alignItems: "flex-end" });
  });

  it("preserves leading indentation while typing a code block", async () => {
    function Harness() {
      const [input, setInput] = useState("");
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }

    const { getByTestId } = await render(<Harness />);
    const composerInput = getByTestId("chat-composer-input");

    await fireEvent.changeText(composerInput, " ");
    expect(getByTestId("chat-composer-input").props.value).toBe(" ");
    await fireEvent.changeText(getByTestId("chat-composer-input"), "  const answer = 42;");
    expect(getByTestId("chat-composer-input").props.value).toBe("  const answer = 42;");
  });

  it("bottom-aligns controls only after visible multiline text is entered", async () => {
    const { getByTestId } = await render(
      <ChatComposer {...baseProps} input={"First line\nSecond line"} />,
    );

    await fireEvent(getByTestId("chat-composer-input"), "contentSizeChange", {
      nativeEvent: { contentSize: { width: 240, height: 50 } },
    });

    expect(getByTestId("composer-input-row")).toHaveStyle({ alignItems: "flex-end" });
  });

  it("offers a full-height editor when the multiline input reaches its limit", async () => {
    const { getByTestId, getByLabelText } = await render(
      <ChatComposer
        {...baseProps}
        input={"A long draft\n".repeat(20)}
      />,
    );
    const composerInput = getByTestId("chat-composer-input");

    await fireEvent(composerInput, "contentSizeChange", {
      nativeEvent: { contentSize: { width: 240, height: 190 } },
    });

    expect(composerInput).toHaveStyle({ height: 164 });
    expect(getByTestId("composer-expand").props.accessibilityState).toEqual({
      expanded: false,
    });

    await fireEvent.press(getByLabelText("rich.expand"));

    expect(getByTestId("composer-expand").props.accessibilityState).toEqual({
      expanded: true,
    });
    expect(getByTestId("chat-composer")).toHaveStyle({ top: 8 });
    expect(getByTestId("chat-composer-input")).toHaveStyle({
      flex: 1,
      minHeight: 0,
    });
    expect(getByLabelText("rich.collapse")).toBeTruthy();
  });

  it("uses Ionicon send and stop glyphs instead of text arrows", async () => {
    const { queryByText, getByLabelText, rerender } = await render(
      <ChatComposer {...baseProps} input="hi" />,
    );
    expect(queryByText("↑")).toBeNull();
    expect(getByLabelText("chat.send_a11y")).toBeTruthy();

    await rerender(<ChatComposer {...baseProps} input="hi" streaming />);
    expect(queryByText("■")).toBeNull();
    expect(getByLabelText("chat.stop_a11y")).toBeTruthy();
  });

  it("hides the math pill when the chat is not about math", async () => {
    const { queryByTestId } = await render(
      <ChatComposer {...baseProps} mathContext={false} input="" />,
    );
    expect(queryByTestId("math-keyboard-toggle")).toBeNull();
  });

  it("shows the math pill when the draft looks like math", async () => {
    const { getByTestId } = await render(
      <ChatComposer {...baseProps} mathContext={false} input={"$\\sqrt{9}$"} />,
    );
    expect(getByTestId("math-keyboard-toggle")).toBeTruthy();
  });

  it("reserves a gap above the floating math chip so action icons are not flush", async () => {
    const onMathChromeHeightChange = jest.fn();
    await render(
      <ChatComposer
        {...baseProps}
        onMathChromeHeightChange={onMathChromeHeightChange}
      />,
    );
    await waitFor(() => {
      expect(onMathChromeHeightChange).toHaveBeenLastCalledWith(56);
    });
  });

  it("toggles the symbol bar and inserts a fraction at the caret", async () => {
    const onChangeInput = jest.fn();
    const { getByTestId, queryByTestId } = await render(
      <ChatComposer {...baseProps} onChangeInput={onChangeInput} />,
    );

    expect(queryByTestId("math-key-frac")).toBeNull();
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    expect(getByTestId("math-keyboard-pad")).toBeTruthy();
    expect(queryByTestId("math-keyboard-toggle")).toBeNull();
    expect(getByTestId("math-keyboard-abc")).toBeTruthy();
    expect(getByTestId("math-composer-caret")).toBeTruthy();
    expect(getByTestId("math-key-frac")).toBeTruthy();

    await fireEvent.press(getByTestId("math-key-frac"));
    expect(onChangeInput).toHaveBeenCalledWith("$\\frac{}{}$");
    expect(getByTestId("math-keyboard-pad")).toBeTruthy();
  });

  it("switches tabs to reach trig functions", async () => {
    const onChangeInput = jest.fn();
    const { getByTestId, queryByTestId } = await render(
      <ChatComposer {...baseProps} onChangeInput={onChangeInput} />,
    );
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    expect(queryByTestId("math-key-sin")).toBeNull();
    await fireEvent.press(getByTestId("math-keyboard-tab-trig"));
    expect(getByTestId("math-key-sin")).toBeTruthy();
    await fireEvent.press(getByTestId("math-key-sin"));
    expect(onChangeInput).toHaveBeenCalledWith("$\\sin()$");
  });

  it("renders a trig function once, not as a doubled name", async () => {
    function Harness() {
      const [input, setInput] = useState("");
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId, getAllByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-keyboard-tab-trig"));
    await fireEvent.press(getByTestId("math-key-cos"));
    expect(getAllByTestId("math-group")).toHaveLength(1);
  });

  it("sends a convert prompt on Ask, not a computed answer", async () => {
    const onChangeInput = jest.fn();
    const onSend = jest.fn();
    const { getByTestId, queryByTestId } = await render(
      <ChatComposer {...baseProps} onChangeInput={onChangeInput} onSend={onSend} />,
    );
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-keyboard-tab-converter"));
    expect(getByTestId("math-converter")).toBeTruthy();
    expect(queryByTestId("math-keyboard-numpad")).toBeNull();
    expect(getByTestId("math-converter-from-value").props.children).toBe("1");
    expect(getByTestId("math-converter-to-value").props.children).toBe("100");
    await fireEvent.press(getByTestId("math-converter-5"));
    expect(getByTestId("math-converter-from-value").props.children).toBe("5");
    expect(getByTestId("math-converter-to-value").props.children).toBe("500");
    await fireEvent.press(getByTestId("math-converter-ask"));
    expect(onSend).toHaveBeenCalledWith("convert 5 m to cm");
    expect(onChangeInput).not.toHaveBeenCalledWith("convert 5 m to cm");
    expect(getByTestId("math-converter")).toBeTruthy();
  });

  it("keeps math navigation and converter controls at least 44pt", async () => {
    const { getByTestId } = await render(<ChatComposer {...baseProps} />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));

    expect(getByTestId("math-keyboard-tab-basics")).toHaveStyle({ minHeight: 44 });
    expect(getByTestId("math-key-caret-left")).toHaveStyle({
      minWidth: 44,
      minHeight: 44,
    });
    expect(getByTestId("math-keyboard-abc")).toHaveStyle({ minHeight: 44 });

    await fireEvent.press(getByTestId("math-keyboard-tab-converter"));
    expect(getByTestId("math-converter-5")).toHaveStyle({ minHeight: 44 });
    expect(getByTestId("math-converter-swap")).toHaveStyle({
      minWidth: 44,
      minHeight: 44,
    });
    expect(getByTestId("math-converter-from-unit")).toHaveStyle({ minHeight: 44 });

    await fireEvent.press(getByTestId("math-converter-from-unit"));
    expect(getByTestId("math-converter-picker-close")).toHaveStyle({
      minWidth: 44,
      minHeight: 44,
    });
    expect(getByTestId("math-converter-cat-length")).toHaveStyle({ minHeight: 44 });
  });

  it("inserts the converter result into the composer as math", async () => {
    let latest = "";
    function Harness() {
      const [input, setInput] = useState("");
      latest = input;
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-keyboard-tab-converter"));
    await fireEvent.press(getByTestId("math-converter-insert"));
    expect(latest).toBe("$100\\,\\text{cm}$");
  });

  it("turns Ask into Stop while a reply is generating", async () => {
    const onSend = jest.fn();
    const onStop = jest.fn();
    const { getByTestId, getByLabelText } = await render(
      <ChatComposer {...baseProps} streaming onSend={onSend} onStop={onStop} />,
    );
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-keyboard-tab-converter"));
    expect(getByLabelText("chat.stop")).toBeTruthy();
    await fireEvent.press(getByTestId("math-converter-ask"));
    expect(onStop).toHaveBeenCalled();
    expect(onSend).not.toHaveBeenCalled();
  });

  it("reopens the Converter tab after ABC", async () => {
    const { getByTestId, queryByTestId } = await render(<ChatComposer {...baseProps} />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-keyboard-tab-converter"));
    expect(getByTestId("math-converter")).toBeTruthy();
    await fireEvent.press(getByTestId("math-keyboard-abc"));
    expect(queryByTestId("math-converter")).toBeNull();
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    expect(getByTestId("math-converter")).toBeTruthy();
  });

  it("opens the unit list in a sheet, not inside the pad", async () => {
    const { getByTestId, queryByTestId } = await render(<ChatComposer {...baseProps} />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-keyboard-tab-converter"));
    expect(queryByTestId("math-converter-picker")).toBeNull();
    await fireEvent.press(getByTestId("math-converter-from-unit"));
    expect(getByTestId("math-converter-picker")).toBeTruthy();
    expect(getByTestId("math-converter-unit-km")).toBeTruthy();
    expect(getByTestId("math-converter-numpad")).toBeTruthy();
    const lengthHeight = StyleSheet.flatten(getByTestId("math-converter-picker").props.style).height;
    await fireEvent.press(getByTestId("math-converter-cat-speed"));
    expect(getByTestId("math-converter-unit-kmh")).toBeTruthy();
    await fireEvent.press(getByTestId("math-converter-cat-temperature"));
    expect(getByTestId("math-converter-unit-c")).toBeTruthy();
    expect(StyleSheet.flatten(getByTestId("math-converter-picker").props.style).height).toBe(
      lengthHeight,
    );
  });

  it("hides the number pad on Trig, Calc, and Greek until 123", async () => {
    const { getByTestId, queryByTestId } = await render(<ChatComposer {...baseProps} />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    expect(getByTestId("math-keyboard-numpad")).toBeTruthy();
    expect(queryByTestId("math-keyboard-123")).toBeNull();
    await fireEvent.press(getByTestId("math-keyboard-tab-trig"));
    expect(queryByTestId("math-keyboard-numpad")).toBeNull();
    expect(getByTestId("math-key-arccos")).toBeTruthy();
    expect(getByTestId("math-key-arccot")).toBeTruthy();
    expect(getByTestId("math-key-rad")).toBeTruthy();
    expect(getByTestId("math-key-arcsinh")).toBeTruthy();
    expect(getByTestId("math-key-arccosh")).toBeTruthy();
    expect(getByTestId("math-key-digit-1")).toBeTruthy();
    expect(getByTestId("math-key-digit-7")).toBeTruthy();
    expect(queryByTestId("math-key-log")).toBeNull();
    expect(getByTestId("math-keyboard-123")).toBeTruthy();
    await fireEvent.press(getByTestId("math-keyboard-123"));
    expect(getByTestId("math-keyboard-numpad")).toBeTruthy();
    expect(getByTestId("math-key-digit-7")).toBeTruthy();
    expect(getByTestId("math-key-trig-theta")).toBeTruthy();
    expect(getByTestId("math-key-trig-pi")).toBeTruthy();
    expect(queryByTestId("math-key-arccos")).toBeNull();
    await fireEvent.press(getByTestId("math-keyboard-123"));
    expect(queryByTestId("math-keyboard-numpad")).toBeNull();
    expect(getByTestId("math-key-arccos")).toBeTruthy();
    await fireEvent.press(getByTestId("math-keyboard-tab-calc"));
    expect(queryByTestId("math-keyboard-numpad")).toBeNull();
    expect(getByTestId("math-key-der")).toBeTruthy();
    expect(getByTestId("math-key-log")).toBeTruthy();
    expect(getByTestId("math-key-oint")).toBeTruthy();
    expect(getByTestId("math-key-vec")).toBeTruthy();
    expect(getByTestId("math-key-ddv")).toBeTruthy();
    await fireEvent.press(getByTestId("math-keyboard-tab-greek"));
    expect(queryByTestId("math-keyboard-numpad")).toBeNull();
    expect(queryByTestId("math-key-digit-7")).toBeNull();
    expect(getByTestId("math-key-alpha")).toBeTruthy();
    expect(getByTestId("math-key-lambda")).toBeTruthy();
    expect(getByTestId("math-key-Omega")).toBeTruthy();
    expect(getByTestId("math-key-backspace")).toBeTruthy();
  });

  it("renders the draft as math, not raw LaTeX", async () => {
    const { getByTestId } = await render(
      <ChatComposer {...baseProps} input={"$\\frac{1}{2}$"} />,
    );
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    expect(getByTestId("math-draft-preview")).toBeTruthy();
    expect(getByTestId("math-frac")).toBeTruthy();
    expect(getByTestId("math-vinculum")).toBeTruthy();
  });

  it("does not render a pasted physics word problem as stacked math", async () => {
    const pasted =
      "A car starts from rest and accelerates at a constant rate of 1.2 m/s². How long does it take the car to travel a distance of 500 meters?";
    const { queryByTestId } = await render(
      <ChatComposer {...baseProps} input={pasted} />,
    );
    expect(queryByTestId("math-draft-preview")).toBeNull();
  });

  it("puts the caret in the numerator, then continues the expression after the fraction", async () => {
    let latest = "";
    function Harness() {
      const [input, setInput] = useState("");
      latest = input;
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-key-frac"));
    expect(getByTestId("math-slot-num-caret")).toBeTruthy();
    expect(getByTestId("math-slot-den-placeholder")).toBeTruthy();
    await fireEvent.press(getByTestId("math-key-digit-1"));
    await fireEvent.press(getByTestId("math-slot-den"));
    await fireEvent.press(getByTestId("math-key-digit-2"));
    expect(getByTestId("math-slot-num")).toBeTruthy();
    expect(getByTestId("math-slot-den")).toBeTruthy();
    await fireEvent.press(getByTestId("math-key-times"));
    await fireEvent.press(getByTestId("math-key-digit-2"));
    expect(latest).toBe("$\\frac{1}{2}\\times 2$");
    expect(getByTestId("math-slot-after")).toBeTruthy();
  });

  it("tabs to the denominator and back to the numerator", async () => {
    function Harness() {
      const [input, setInput] = useState("");
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId, queryByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-key-frac"));
    expect(getByTestId("math-slot-num-caret")).toBeTruthy();
    await fireEvent.press(getByTestId("math-slot-den"));
    expect(getByTestId("math-slot-den-caret")).toBeTruthy();
    expect(queryByTestId("math-slot-num-caret")).toBeNull();
    await fireEvent.press(getByTestId("math-slot-num"));
    expect(getByTestId("math-slot-num-caret")).toBeTruthy();
  });

  it("does not show raw latex after deleting an empty cos", async () => {
    let latest = "";
    function Harness() {
      const [input, setInput] = useState("");
      latest = input;
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId, queryByText } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-keyboard-tab-trig"));
    await fireEvent.press(getByTestId("math-key-cos"));
    await fireEvent.press(getByTestId("math-key-backspace"));
    expect(latest).not.toMatch(/\\cos/);
    expect(queryByText("\\cos")).toBeNull();
  });

  it("shows a tappable box for square root, not only for fractions", async () => {
    function Harness() {
      const [input, setInput] = useState("");
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-key-sqrt"));
    expect(getByTestId("math-slot-sqrt-caret")).toBeTruthy();
  });

  it("keeps the radical bar after a digit is typed into the root", async () => {
    function Harness() {
      const [input, setInput] = useState("");
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId, queryByText } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-key-sqrt"));
    await fireEvent.press(getByTestId("math-key-digit-8"));
    expect(getByTestId("math-sqrt")).toBeTruthy();
    expect(getByTestId("math-sqrt-radicand")).toBeTruthy();
    expect(getByTestId("math-slot-sqrt")).toBeTruthy();
    expect(queryByText(/\\sqrt/)).toBeNull();
  });

  it("ⁿ√ opens an nth-root index box", async () => {
    function Harness() {
      const [input, setInput] = useState("");
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-key-nroot"));
    expect(getByTestId("math-slot-nroot-index")).toBeTruthy();
  });

  it("moves into the radicand after filling the nth-root index with π", async () => {
    function Harness() {
      const [input, setInput] = useState("");
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId, queryByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-key-nroot"));
    expect(getByTestId("math-slot-nroot-index-caret")).toBeTruthy();
    await fireEvent.press(getByTestId("math-key-pi"));
    expect(queryByTestId("math-slot-nroot-index-caret")).toBeNull();
    expect(getByTestId("math-slot-sqrt-caret")).toBeTruthy();
  });

  it("second ⁿ√ tap moves from a filled index into the radicand", async () => {
    function Harness() {
      const [input, setInput] = useState("");
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-key-nroot"));
    await fireEvent.press(getByTestId("math-key-digit-3"));
    expect(getByTestId("math-slot-nroot-index-caret-end")).toBeTruthy();
    await fireEvent.press(getByTestId("math-key-nroot"));
    expect(getByTestId("math-slot-sqrt-caret")).toBeTruthy();
  });

  it("° on an empty composer inserts a base box", async () => {
    let latest = "";
    function Harness() {
      const [input, setInput] = useState("");
      latest = input;
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-keyboard-tab-trig"));
    await fireEvent.press(getByTestId("math-key-deg"));
    expect(latest).toBe("$^{\\circ}$");
    await fireEvent.press(getByTestId("math-key-digit-3"));
    expect(latest).toBe("$3^{\\circ}$");
  });

  it("logₙ auto-advances from the base into the argument after π", async () => {
    let latest = "";
    function Harness() {
      const [input, setInput] = useState("");
      latest = input;
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-keyboard-tab-calc"));
    await fireEvent.press(getByTestId("math-key-logn"));
    await fireEvent.press(getByTestId("math-keyboard-tab-basics"));
    await fireEvent.press(getByTestId("math-key-pi"));
    expect(latest).toBe("$\\log_{\\pi }()$");
    expect(getByTestId("math-slot-group-caret")).toBeTruthy();
  });

  it("types a comma and y from the number pad", async () => {
    function Harness() {
      const [input, setInput] = useState("");
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-key-var-y"));
    await fireEvent.press(getByTestId("math-key-comma"));
    expect(getByTestId("chat-composer-input").props.value).toBe("$y,$");
  });

  it("shows a gray box for the empty exponent until it is focused", async () => {
    function Harness() {
      const [input, setInput] = useState("");
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId, queryByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-key-sup"));
    expect(getByTestId("math-slot-sup-caret")).toBeTruthy();
    expect(queryByTestId("math-slot-sup-placeholder")).toBeNull();
  });

  it("xⁿ on an empty composer shows a base x and an exponent box", async () => {
    let latest = "";
    function Harness() {
      const [input, setInput] = useState("");
      latest = input;
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-key-sup"));
    expect(latest).toBe("$x^{}$");
    expect(getByTestId("math-draft-preview")).toBeTruthy();
    expect(getByTestId("math-sup")).toBeTruthy();
    expect(getByTestId("math-slot-sup-caret")).toBeTruthy();
  });

  it("shows a caret in the subscript box", async () => {
    function Harness() {
      const [input, setInput] = useState("");
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-key-sub"));
    expect(getByTestId("math-slot-sub-caret")).toBeTruthy();
  });

  it("moves the blue caret to the denominator when that box is tapped", async () => {
    function Harness() {
      const [input, setInput] = useState("");
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId, queryByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-key-frac"));
    expect(getByTestId("math-slot-num-caret")).toBeTruthy();
    expect(getByTestId("math-slot-den-placeholder")).toBeTruthy();
    await fireEvent.press(getByTestId("math-slot-den"));
    expect(queryByTestId("math-slot-num-caret")).toBeNull();
    expect(getByTestId("math-slot-num-placeholder")).toBeTruthy();
    expect(getByTestId("math-slot-den-caret")).toBeTruthy();
  });

  it("backspaces a fraction without showing raw LaTeX", async () => {
    let latest = "";
    function Harness() {
      const [input, setInput] = useState("");
      latest = input;
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId, queryByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-key-frac"));
    await fireEvent.press(getByTestId("math-key-digit-8"));
    await fireEvent.press(getByTestId("math-slot-den"));
    await fireEvent.press(getByTestId("math-key-digit-8"));
    await fireEvent.press(getByTestId("math-key-backspace"));
    expect(latest).toBe("$\\frac{8}{}$");
    expect(getByTestId("math-frac")).toBeTruthy();
    await fireEvent.press(getByTestId("math-key-backspace"));
    expect(latest).toBe("$\\frac{}{}$");
    await fireEvent.press(getByTestId("math-key-backspace"));
    expect(latest).toBe("");
    expect(queryByTestId("math-draft-preview")).toBeNull();
  });

  it("lets you tap the front of the draft and delete the first digit", async () => {
    let latest = "";
    function Harness() {
      const [input, setInput] = useState("");
      latest = input;
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-key-frac"));
    await fireEvent.press(getByTestId("math-key-digit-8"));
    await fireEvent.press(getByTestId("math-slot-den"));
    await fireEvent.press(getByTestId("math-key-digit-8"));
    await fireEvent.press(getByTestId("math-slot-before"));
    expect(getByTestId("math-slot-before-caret")).toBeTruthy();
    await fireEvent.press(getByTestId("math-key-backspace"));
    expect(latest).toBe("$\\frac{}{8}$");
  });

  it("inserts at the tapped end of the draft, not the start", async () => {
    let latest = "$|5|99$";
    function Harness() {
      const [input, setInput] = useState("$|5|99$");
      latest = input;
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId, queryByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    expect(getByTestId("math-slot-before-caret")).toBeTruthy();
    expect(queryByTestId("math-slot-after-caret")).toBeNull();
    await fireEvent.press(getByTestId("math-slot-after"));
    expect(queryByTestId("math-slot-before-caret")).toBeNull();
    expect(getByTestId("math-slot-after-caret")).toBeTruthy();
    await fireEvent.press(getByTestId("math-key-digit-7"));
    expect(latest).toBe("$|5|997$");
  });

  it("ABC keeps the visual fraction and parks the caret after it", async () => {
    let latest = "";
    function Harness() {
      const [input, setInput] = useState("");
      latest = input;
      return <ChatComposer {...baseProps} input={input} onChangeInput={setInput} />;
    }
    const { getByTestId, queryByTestId } = await render(<Harness />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-key-frac"));
    await fireEvent.press(getByTestId("math-key-digit-9"));
    expect(getByTestId("math-slot-num-caret-end")).toBeTruthy();
    await fireEvent.press(getByTestId("math-keyboard-abc"));
    expect(getByTestId("math-draft-preview")).toBeTruthy();
    expect(getByTestId("math-frac")).toBeTruthy();
    expect(queryByTestId("math-key-frac")).toBeNull();
    expect(queryByTestId("math-slot-num-caret-end")).toBeNull();
    expect(getByTestId("math-slot-after-caret")).toBeTruthy();
    await fireEvent.press(getByTestId("math-slot-before"));
    expect(getByTestId("math-slot-before-caret")).toBeTruthy();
    const before = latest;
    const denTyped = before.replace("}{}", "}{g}");
    await fireEvent.changeText(getByTestId("chat-composer-input"), denTyped);
    expect(latest.startsWith("g")).toBe(true);
    expect(latest).toContain("\\frac{9}{}");
    expect(latest).not.toContain("\\frac{9}{g}");
  });

  it("hides the bar when toggled off", async () => {
    const { getByTestId, queryByTestId } = await render(<ChatComposer {...baseProps} />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    expect(getByTestId("math-key-frac")).toBeTruthy();
    await fireEvent.press(getByTestId("math-keyboard-abc"));
    expect(queryByTestId("math-key-frac")).toBeNull();
  });

  it("rewrites × through the math-bar Paste control", async () => {
    (Clipboard.getStringAsync as jest.Mock).mockResolvedValue("2 × 3");
    const onChangeInput = jest.fn();
    const { getByTestId } = await render(
      <ChatComposer {...baseProps} onChangeInput={onChangeInput} />,
    );
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    await fireEvent.press(getByTestId("math-keyboard-paste"));
    await waitFor(() => {
      expect(onChangeInput).toHaveBeenCalledWith("$2 \\times 3$");
    });
  });

  it("does not offer the math scanner just because the composer focused", async () => {
    (Clipboard.getStringAsync as jest.Mock).mockResolvedValue("");
    (Clipboard.hasImageAsync as jest.Mock).mockResolvedValue(true);
    const { getByTestId, queryByText } = await render(
      <ChatComposer {...baseProps} onOpenMathScanner={jest.fn()} />,
    );
    fireEvent(getByTestId("chat-composer-input"), "focus");
    await waitFor(() => {
      expect(queryByText("chat.math_paste_scan_hint")).toBeNull();
    });
  });

  it("hides the draft token hint for a short message", async () => {
    const { queryByTestId } = await render(<ChatComposer {...baseProps} input="hi" />);
    expect(queryByTestId("composer-token-hint")).toBeNull();
  });

  it("shows the draft token hint when the estimate is large", async () => {
    const { getByTestId } = await render(
      <ChatComposer {...baseProps} input={"a".repeat(400)} />,
    );
    expect(getByTestId("composer-token-hint")).toBeTruthy();
  });

  it("shows live talk when a handler is provided", async () => {
    const onLiveTalkPress = jest.fn();
    const { getByTestId } = await render(
      <ChatComposer {...baseProps} onLiveTalkPress={onLiveTalkPress} />,
    );
    fireEvent.press(getByTestId("live-talk-button"));
    expect(onLiveTalkPress).toHaveBeenCalled();
  });

  it("hides live talk when the send button is showing", async () => {
    const { queryByTestId } = await render(
      <ChatComposer {...baseProps} input="hello" onLiveTalkPress={jest.fn()} />,
    );
    expect(queryByTestId("live-talk-button")).toBeNull();
  });

  it("keeps type and attach and puts mute next to close in live talk", async () => {
    const onYield = jest.fn();
    const { getByTestId, getByLabelText, queryByTestId } = await render(
      <ChatComposer
        {...baseProps}
        onLiveTalkPress={jest.fn()}
        liveTalkChrome={{
          muted: false,
          onClose: jest.fn(),
          onMutePress: jest.fn(),
          onYield,
        }}
      />,
    );
    expect(queryByTestId("live-talk-button")).toBeNull();
    expect(getByTestId("live-talk-mute")).toBeTruthy();
    expect(getByTestId("live-talk-close")).toBeTruthy();
    expect(getByTestId("chat-composer-input")).toBeTruthy();
    expect(getByLabelText("chat.attach_a11y")).toBeTruthy();
    expect(getByTestId("composer-attachment-add-icon").props.name).toBe("plus");
  });

  it("hides mute and close while the user is typing in live talk", async () => {
    const chrome = {
      muted: false,
      onClose: jest.fn(),
      onMutePress: jest.fn(),
      onYield: jest.fn(),
    };
    const { queryByTestId, rerender } = await render(
      <ChatComposer
        {...baseProps}
        input="hello"
        onLiveTalkPress={jest.fn()}
        liveTalkChrome={chrome}
      />,
    );
    expect(queryByTestId("live-talk-mute")).toBeNull();
    expect(queryByTestId("live-talk-close")).toBeNull();
    expect(queryByTestId("chat-composer-input")).toBeTruthy();

    await rerender(
      <ChatComposer
        {...baseProps}
        input=""
        onLiveTalkPress={jest.fn()}
        liveTalkChrome={chrome}
        pendingAttachment={{
          kind: "image",
          localUri: "file://photo.jpg",
          contentType: "image/jpeg",
          fileName: "photo.jpg",
        }}
      />,
    );
    expect(queryByTestId("live-talk-mute")).toBeTruthy();
    expect(queryByTestId("live-talk-close")).toBeTruthy();
  });
});
