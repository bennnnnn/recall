import { act, fireEvent, render } from "@testing-library/react-native";
import { Text } from "react-native";

import { CodeBlock } from "@/components/CodeBlock";

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
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
// The real Prism tokenizer loads through a dynamic import(); a one-token
// stand-in keeps the card's layout under test.
jest.mock("@/lib/codeTokenize", () => ({
  tokenize: (code: string) => [{ text: code, color: "#111111" }],
  resolveHighlightLang: (lang: string) => lang,
}));

const CODE = 'person = {"name": "Bini", "age": 25}';

async function renderBlock(props: Partial<Parameters<typeof CodeBlock>[0]> = {}) {
  const utils = await render(<CodeBlock code={CODE} lang="python" {...props} />);
  // Let the tokenizer import settle.
  await act(async () => {
    await Promise.resolve();
  });
  return utils;
}

describe("CodeBlock", () => {
  it("shows the code with a floating copy button and no language label", async () => {
    const { getByText, queryByText, getByLabelText, getByTestId } = await renderBlock();

    expect(getByText(CODE)).toBeOnTheScreen();
    expect(queryByText("python")).toBeNull();
    expect(getByTestId("code-block-actions")).toContainElement(getByLabelText("common.copy"));
  });

  it("puts extra actions in the same corner", async () => {
    const { getByTestId, getByText } = await renderBlock({
      headerExtra: <Text>preview</Text>,
    });

    expect(getByTestId("code-block-actions")).toContainElement(getByText("preview"));
  });

  it("keeps every corner action clear of the end of a line", async () => {
    const { getByTestId } = await renderBlock({ headerExtra: <Text>preview</Text> });
    // Before layout: room for the copy button alone.
    expect(getByTestId("code-block-lines")).toHaveStyle({ paddingRight: 16 + 40 });

    // Preview (44) + gap + copy: the gutter follows the measured group.
    await fireEvent(getByTestId("code-block-actions"), "layout", {
      nativeEvent: { layout: { x: 0, y: 0, width: 82, height: 32 } },
    });
    expect(getByTestId("code-block-lines")).toHaveStyle({ paddingRight: 16 + 82 });
  });

  it("has no corner actions when copy is off", async () => {
    const { queryByTestId, queryByLabelText } = await renderBlock({ showCopy: false });

    expect(queryByLabelText("common.copy")).toBeNull();
    expect(queryByTestId("code-block-actions")).toBeNull();
  });

  it("shows plain code without copy while the fence is still streaming", async () => {
    const { getByText, queryByLabelText } = await renderBlock({ streaming: true });

    expect(getByText(CODE)).toBeOnTheScreen();
    expect(queryByLabelText("common.copy")).toBeNull();
  });
});
