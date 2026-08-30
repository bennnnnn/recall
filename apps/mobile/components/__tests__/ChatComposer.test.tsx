import { useState } from "react";
import { StyleSheet } from "react-native";
import * as Clipboard from "expo-clipboard";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import { ChatComposer } from "@/components/chat/ChatComposer";

jest.mock("expo-clipboard", () => ({
  setStringAsync: jest.fn(),
  getStringAsync: jest.fn(async () => ""),
  hasImageAsync: jest.fn(async () => false),
  getImageAsync: jest.fn(),
}));

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
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

jest.mock("@/components/SuggestedRemindersNudge", () => ({
  SuggestedRemindersNudge: () => null,
}));

jest.mock("@/components/chat/VoiceComposerWaveform", () => ({
  VoiceComposerWaveform: () => null,
}));

jest.mock("@/components/chat/VoiceMicButton", () => ({
  VoiceMicButton: () => null,
}));

jest.mock("@/components/chat/LiveTalkButton", () => {
  const { Pressable } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    LiveTalkButton: ({ onPress }: { onPress: () => void }) => (
      <Pressable testID="live-talk-button" onPress={onPress} />
    ),
  };
});

jest.mock("@/components/ComposerAttachmentPreview", () => ({
  ComposerAttachmentPreview: () => null,
}));

const baseProps = {
  visible: true,
  token: "t",
  input: "",
  onChangeInput: jest.fn(),
  streaming: false,
  attachBusy: false,
  pendingAttachment: null,
  onRemoveAttachment: jest.fn(),
  editingMessageId: null,
  onCancelEdit: jest.fn(),
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

  it("ABC keeps the visual fraction and lets you type words in front of it", async () => {
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
  });
});
