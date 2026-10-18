import { useState } from "react";
import { Dimensions, StyleSheet } from "react-native";
import { act, fireEvent, render, waitFor, within } from "@testing-library/react-native";

import { ChatComposer } from "@/features/chat/components/ChatComposer";
import { MATH_KEYBOARD_GAP_FADE_HEIGHT } from "@/features/chat/components/chatComposerStyles";
import { KEY_HEIGHT_MIN, mathPadHeight, padKeyHeight } from "@/lib/math/keyboardPad";
import { darkTheme, lightTheme } from "@/lib/theme";
import { ComposerDraftProvider, useComposerDraftApi } from "@/contexts/ComposerDraftContext";

jest.mock("expo-linear-gradient", () => {
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  return { LinearGradient: View };
});

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

jest.mock("@/features/speech/components/VoiceMicButton", () => {
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    VoiceMicButton: () => <View testID="voice-mic-button" />,
  };
});

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

// The RN jest preset reports a 2x text size. Sizes here are at the default
// unless a test raises it; the preset's other window metrics stay.
const presetDimensionsGet = Dimensions.get.bind(Dimensions);
let windowFontScale = 1;
jest
  .spyOn(Dimensions, "get")
  .mockImplementation((dim) => ({ ...presetDimensionsGet(dim), fontScale: windowFontScale }));
beforeEach(() => {
  windowFontScale = 1;
});

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
    expect(getByTestId("chat-composer-input")).toHaveStyle({ height: 112, paddingTop: 0 });

    await fireEvent.press(getByLabelText("chat.send_a11y"));

    await waitFor(() => {
      expect(getByTestId("chat-composer-input").props.value).toBe("");
      expect(getByTestId("chat-composer-input")).toHaveStyle({ height: 24 });
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
    expect(composerInput.props.accessibilityLabel).toBe("chat.placeholder");
    expect(composerInput.props.maxFontSizeMultiplier).toBe(1.5);

    await fireEvent.changeText(composerInput, "\n");
    await fireEvent(composerInput, "contentSizeChange", {
      nativeEvent: { contentSize: { width: 240, height: 50 } },
    });

    expect(getByTestId("chat-composer-input").props.value).toBe("\n");
    expect(getByTestId("chat-composer-input").props.placeholder).toBe("chat.placeholder");
    expect(getByTestId("chat-composer-input")).toHaveStyle({ height: 48, paddingTop: 0 });
    expect(getByTestId("composer-input-row")).toHaveStyle({ alignItems: "flex-end" });
  });

  it("grows to the next line when text reaches the end of the field", async () => {
    const { getByTestId } = await render(
      <ChatComposer {...baseProps} input={"a".repeat(40)} />,
    );
    expect(getByTestId("chat-composer-input")).toHaveStyle({ height: 24 });

    await fireEvent(getByTestId("chat-composer-input"), "layout", {
      nativeEvent: { layout: { x: 0, y: 0, width: 200, height: 44 } },
    });

    expect(getByTestId("chat-composer-input")).toHaveStyle({
      height: 48,
      paddingTop: 0,
    });
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

  it("gives wrapped text the full width and moves the buttons to a row under it", async () => {
    const view = await render(<ChatComposer {...baseProps} input="Short" />);
    const row = () => view.getByTestId("composer-input-row");
    expect(within(row()).getByTestId("composer-attachment-button")).toBeTruthy();
    expect(view.queryByTestId("composer-stacked-controls")).toBeNull();

    await view.rerender(
      <ChatComposer {...baseProps} input={"A long message that wraps ".repeat(4)} />,
    );
    await fireEvent(view.getByTestId("chat-composer-input"), "contentSizeChange", {
      nativeEvent: { contentSize: { width: 240, height: 50 } },
    });
    const controls = view.getByTestId("composer-stacked-controls");
    expect(within(controls).getByTestId("composer-attachment-button")).toBeTruthy();
    expect(within(controls).getByLabelText("chat.send_a11y")).toBeTruthy();
    expect(within(row()).queryByTestId("composer-attachment-button")).toBeNull();

    // Shorter text that would fit stays stacked; only a cleared draft goes back to one row.
    await view.rerender(<ChatComposer {...baseProps} input="Short" />);
    expect(view.getByTestId("composer-stacked-controls")).toBeTruthy();
    await view.rerender(<ChatComposer {...baseProps} input="" />);
    expect(view.queryByTestId("composer-stacked-controls")).toBeNull();
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

    expect(composerInput).toHaveStyle({ height: 144, paddingTop: 0 });
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

  it("shows the math keyboard button on an empty composer, immediately before the mic", async () => {
    const { getByTestId } = await render(
      <ChatComposer
        {...baseProps}
        input=""
        voiceAvailable
        onVoicePress={jest.fn()}
      />,
    );
    const row = getByTestId("composer-input-row");
    const ids: string[] = [];
    const walk = (node: { props?: { testID?: string }; children?: unknown[] }) => {
      const id = node.props?.testID;
      if (typeof id === "string") ids.push(id);
      for (const child of node.children ?? []) {
        if (child && typeof child === "object") walk(child as typeof node);
      }
    };
    walk(row);
    const math = ids.indexOf("math-keyboard-toggle");
    const mic = ids.indexOf("voice-mic-button");
    expect(math).toBeGreaterThanOrEqual(0);
    expect(mic).toBe(math + 1);
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
    expect(getByTestId("math-converter-from-value").props.children).toBe("1");
    expect(getByTestId("math-converter-to-value").props.children).toBe("100");
    await fireEvent.press(getByTestId("math-converter-5"));
    expect(getByTestId("math-converter-from-value").props.children).toBe("5");
    expect(getByTestId("math-converter-to-value").props.children).toBe("500");
    await fireEvent.press(getByTestId("math-converter-ask"));
    expect(onSend).toHaveBeenCalledWith("convert 5 m to cm");
    expect(onChangeInput).not.toHaveBeenCalledWith("convert 5 m to cm");
    expect(queryByTestId("math-converter")).toBeNull();
  });

  it("gives every page, the converter included, one key height of at least 44pt", async () => {
    const { getByTestId } = await render(<ChatComposer {...baseProps} />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    const flat = (id: string) => {
      const style = getByTestId(id).props.style;
      return StyleSheet.flatten(typeof style === "function" ? style({ pressed: false }) : style);
    };
    const keyHeight = padKeyHeight(mathPadHeight(0));
    expect(keyHeight).toBeGreaterThanOrEqual(KEY_HEIGHT_MIN);
    expect(getByTestId("math-keyboard-tab-basics")).toHaveStyle({ minHeight: 44 });
    expect(getByTestId("math-keyboard-abc")).toHaveStyle({ minHeight: 44 });
    for (const id of ["math-key-frac", "math-key-digit-7", "math-key-left", "math-key-right"]) {
      expect(flat(id).height).toBe(keyHeight);
    }
    await fireEvent.press(getByTestId("math-keyboard-tab-calc"));
    expect(flat("math-key-partial-x").height).toBe(keyHeight);
    await fireEvent.press(getByTestId("math-keyboard-tab-symbols"));
    expect(flat("math-key-cup").height).toBe(keyHeight);

    await fireEvent.press(getByTestId("math-keyboard-tab-converter"));
    for (const id of ["math-converter-0", "math-converter-dot", "math-converter-ask"]) {
      expect(flat(id).height).toBe(keyHeight);
    }
    expect(flat("math-converter-ask").flex).toBe(2);
    expect(flat("math-converter-from-unit").height).toBe(keyHeight);
    expect(getByTestId("math-converter-swap")).toHaveStyle({ minWidth: 44, minHeight: 44 });

    await fireEvent.press(getByTestId("math-converter-from-unit"));
    expect(getByTestId("math-converter-picker-close")).toHaveStyle({ minWidth: 44, minHeight: 44 });
    expect(getByTestId("math-converter-cat-length")).toHaveStyle({ minHeight: 44 });
  });
  it("draws every key white with the same ink, delete and clear included", async () => {
    const { getByTestId } = await render(<ChatComposer {...baseProps} />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    const flat = (style: unknown) =>
      StyleSheet.flatten(typeof style === "function" ? style({ pressed: false }) : style);
    const ink = [lightTheme.text, darkTheme.text];
    const white = [lightTheme.bg, darkTheme.bg];
    const back = getByTestId("math-key-backspace");
    expect(white).toContain(flat(back.props.style).backgroundColor);
    expect(ink).toContain(within(back).getByTestId("math-key-backspace-icon").props.color);
    await fireEvent.press(getByTestId("math-keyboard-tab-converter"));
    for (const id of ["math-converter-5", "math-converter-ask", "math-converter-AC", "math-converter-±"]) {
      expect(white).toContain(flat(getByTestId(id).props.style).backgroundColor);
    }
    const clear = within(getByTestId("math-converter-AC")).getByText("chat.math_converter_clear");
    expect(ink).toContain(flat(clear.props.style).color);
    const backIcon = within(getByTestId("math-converter-back")).getByTestId("math-converter-back-icon");
    expect(backIcon.props.name).toBe("backspace");
    expect(ink).toContain(backIcon.props.color);
  });
  it("leaves the thread free to scroll while the math keyboard is open", async () => {
    const { getByTestId, queryByTestId } = await render(<ChatComposer {...baseProps} />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    expect(getByTestId("math-keyboard-pad")).toBeTruthy();
    const padHeight = StyleSheet.flatten(getByTestId("math-keyboard-pad").props.style).height;
    const fade = StyleSheet.flatten(getByTestId("composer-scroll-fade").props.style);
    expect(fade.top).toBeUndefined();
    expect(fade.bottom).toBe(padHeight);
    expect(fade.height).toBe(MATH_KEYBOARD_GAP_FADE_HEIGHT);
    expect(StyleSheet.flatten(getByTestId("chat-composer").props.style).top).toBeUndefined();
    expect(queryByTestId("math-keyboard-dismiss")).toBeNull();
    await fireEvent.press(getByTestId("math-keyboard-abc"));
    expect(queryByTestId("math-keyboard-pad")).toBeNull();
    expect(queryByTestId("composer-scroll-fade")).toBeNull();
    await fireEvent(getByTestId("chat-composer-input"), "focus");
    expect(queryByTestId("math-keyboard-pad")).toBeNull();
  });

  it("minimizes the math keyboard while a reply is streaming", async () => {
    const onStop = jest.fn();
    const { getByTestId, getByLabelText, queryByTestId, rerender } = await render(
      <ChatComposer {...baseProps} onStop={onStop} />,
    );
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    expect(getByTestId("math-keyboard-pad")).toBeTruthy();

    await rerender(<ChatComposer {...baseProps} streaming onStop={onStop} />);
    expect(queryByTestId("math-keyboard-pad")).toBeNull();
    expect(getByLabelText("chat.stop_a11y")).toBeTruthy();

    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    expect(queryByTestId("math-keyboard-pad")).toBeNull();
    await fireEvent.press(getByLabelText("chat.stop_a11y"));
    expect(onStop).toHaveBeenCalled();
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

  it("keeps digits and operators on Basics, and every page on the same grid", async () => {
    const { getByTestId, queryByTestId } = await render(<ChatComposer {...baseProps} />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    for (const id of ["digit-7", "digit-0", "plus", "minus", "times", "div", "eq", "var-x", "frac"]) {
      expect(getByTestId(`math-key-${id}`)).toBeTruthy();
    }
    expect(queryByTestId("math-keyboard-123")).toBeNull();
    for (const tab of ["symbols", "trig", "calc", "greek"]) {
      await fireEvent.press(getByTestId(`math-keyboard-tab-${tab}`));
      expect(getByTestId("math-key-left")).toBeTruthy();
      expect(getByTestId("math-key-right")).toBeTruthy();
      expect(getByTestId("math-key-backspace")).toBeTruthy();
      expect(queryByTestId("math-key-digit-7")).toBeNull();
    }
    await fireEvent.press(getByTestId("math-keyboard-tab-trig"));
    for (const id of ["arccot", "sech", "theta", "deg", "pi-over-2", "two-pi"]) {
      expect(getByTestId(`math-key-${id}`)).toBeTruthy();
    }
    await fireEvent.press(getByTestId("math-keyboard-tab-calc"));
    for (const id of ["der", "oint", "binom", "perm", "e-const", "prime"]) {
      expect(getByTestId(`math-key-${id}`)).toBeTruthy();
    }
  });
});
