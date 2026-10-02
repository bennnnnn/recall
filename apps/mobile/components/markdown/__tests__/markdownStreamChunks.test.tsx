import { render } from "@testing-library/react-native";

import { MarkdownContent } from "@/components/MarkdownContent";

jest.mock("@/components/LinkPreviewCard", () => {
  const { Text } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    LinkPreviewCard: ({ url }: { url: string }) => <Text>{url}</Text>,
  };
});

describe("MarkdownContent streaming chunks", () => {
  it("keeps a settled chunk when the live tail grows", async () => {
    const head = `${"Settled prose. ".repeat(40)}\n\n`;
    const grown = `${head}The live tail.\n`;
    const view = await render(<MarkdownContent content={head} streaming />);
    expect(view.getByText(/Settled prose/)).toBeOnTheScreen();
    await view.rerender(<MarkdownContent content={grown} streaming />);
    expect(view.getByText(/Settled prose/)).toBeOnTheScreen();
    expect(view.getByText(/The live tail/)).toBeOnTheScreen();
  });

  it("holds the success check until the answer fence closes", async () => {
    const open = "```answer\nx =\n";
    const view = await render(<MarkdownContent content={open} streaming />);
    expect(view.getByText("x =")).toBeOnTheScreen();
    expect(view.queryByTestId("answer-success-check")).toBeNull();
    await view.rerender(<MarkdownContent content={`${open}\`\`\`\n`} streaming />);
    expect(view.getByTestId("answer-success-check")).toBeOnTheScreen();
  });
});
