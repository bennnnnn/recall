import { useState } from "react";
import { fireEvent, render } from "@testing-library/react-native";

import { ChatComposer } from "@/components/chat/ChatComposer";

jest.mock("expo-clipboard", () => ({
  setStringAsync: jest.fn(),
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

jest.mock("react-native-reanimated", () => {
  const { View } = jest.requireActual("react-native");
  return {
    __esModule: true,
    default: { View },
  };
});

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
};

describe("ChatComposer math keyboard", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("toggles the symbol bar and inserts a fraction at the caret", async () => {
    const onChangeInput = jest.fn();
    const { getByTestId, queryByTestId } = await render(
      <ChatComposer {...baseProps} onChangeInput={onChangeInput} />,
    );

    expect(queryByTestId("math-key-frac")).toBeNull();
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
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

  it("renders the draft as math, not raw LaTeX", async () => {
    const { getByTestId } = await render(
      <ChatComposer {...baseProps} input={"$\\frac{1}{2}$"} />,
    );
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
    await fireEvent.press(getByTestId("math-key-digit-1"));
    await fireEvent.press(getByTestId("math-key-next-slot"));
    await fireEvent.press(getByTestId("math-key-digit-2"));
    expect(getByTestId("math-slot-num")).toBeTruthy();
    expect(getByTestId("math-slot-den")).toBeTruthy();
    await fireEvent.press(getByTestId("math-key-times"));
    await fireEvent.press(getByTestId("math-key-digit-2"));
    expect(latest).toBe("$\\frac{1}{2}\\times 2$");
    expect(getByTestId("math-slot-after")).toBeTruthy();
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
    await fireEvent.press(getByTestId("math-key-next-slot"));
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
    await fireEvent.press(getByTestId("math-key-next-slot"));
    await fireEvent.press(getByTestId("math-key-digit-8"));
    await fireEvent.press(getByTestId("math-slot-before"));
    expect(getByTestId("math-slot-before-caret")).toBeTruthy();
    await fireEvent.press(getByTestId("math-key-backspace"));
    expect(latest).toBe("$\\frac{}{8}$");
  });

  it("hides the bar when toggled off", async () => {
    const { getByTestId, queryByTestId } = await render(<ChatComposer {...baseProps} />);
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    expect(getByTestId("math-key-frac")).toBeTruthy();
    await fireEvent.press(getByTestId("math-keyboard-toggle"));
    expect(queryByTestId("math-key-frac")).toBeNull();
  });
});
