import { act, fireEvent, render } from "@testing-library/react-native";
import * as Clipboard from "expo-clipboard";

import { CopyButton } from "@/components/CopyButton";

jest.mock("expo-clipboard", () => ({
  setStringAsync: jest.fn().mockResolvedValue(true),
}));
jest.mock("expo-haptics", () => ({
  impactAsync: jest.fn(),
  selectionAsync: jest.fn(),
  notificationAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: "Light" },
  NotificationFeedbackType: { Success: "Success", Warning: "Warning" },
}));
jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));
// i18next isn't initialized in the component jest preset; return the key so the
// label is deterministic and decoupled from the English copy.
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

const setStringAsync = Clipboard.setStringAsync as jest.Mock;

async function flushCopied() {
  // onCopy awaits Clipboard.setStringAsync; flush that microtask + the state update.
  await act(async () => {
    await Promise.resolve();
  });
}

describe("CopyButton", () => {
  beforeEach(() => {
    setStringAsync.mockClear();
  });

  it("renders the Copy label and copies on press", async () => {
    const { getByText } = await render(<CopyButton text="hello" />);

    expect(getByText("common.copy")).toBeOnTheScreen();

    await fireEvent.press(getByText("common.copy"));
    await flushCopied();

    expect(setStringAsync).toHaveBeenCalledWith("hello");
  });

  it("shows the Copied label after a successful press", async () => {
    const { getByText } = await render(<CopyButton text="hi" />);

    await fireEvent.press(getByText("common.copy"));
    await flushCopied();

    expect(getByText("common.copied")).toBeOnTheScreen();
  });

  it("resets back to Copy after the timeout", async () => {
    jest.useFakeTimers();
    try {
      const { getByText, queryByText } = await render(<CopyButton text="hi" />);

      await fireEvent.press(getByText("common.copy"));
      await flushCopied();
      expect(getByText("common.copied")).toBeOnTheScreen();

      await act(async () => {
        jest.advanceTimersByTime(1500);
      });

      expect(queryByText("common.copied")).toBeNull();
      expect(getByText("common.copy")).toBeOnTheScreen();
    } finally {
      jest.useRealTimers();
    }
  });

  it("does not copy when the text is blank", async () => {
    const { getByText } = await render(<CopyButton text="   " />);

    await fireEvent.press(getByText("common.copy"));
    await flushCopied();

    expect(setStringAsync).not.toHaveBeenCalled();
  });
});
