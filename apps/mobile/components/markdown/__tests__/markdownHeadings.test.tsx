import { render, screen } from "@testing-library/react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import "@/lib/i18n";

jest.unmock("react-i18next");
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: () => null }));
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  writeAsStringAsync: jest.fn(),
  EncodingType: { UTF8: "utf8" },
}));
jest.mock("@/components/WebPreviewCodeBlock", () => ({ WebPreviewCodeBlock: "WebPreviewCodeBlock" }));
jest.mock("@/components/rich/CircularClockBlock", () => ({ CircularClockBlock: "CircularClockBlock" }));
jest.mock("@/components/rich/AnswerBlock", () => ({ AnswerBlock: "AnswerBlock" }));

describe("markdown headings", () => {
  it("are headings to a screen reader, so its heading navigation can jump between sections", async () => {
    await render(
      <MarkdownContent content={"# Plan\n\n## Step one\n\nDo it.\n\n### Notes with `code`\n\nMore."} />,
    );

    const headers = screen.getAllByRole("header");
    expect(headers).toHaveLength(3);
    expect(screen.getByRole("header", { name: "Step one" })).toBeOnTheScreen();
    // Body text stays plain text.
    expect(screen.queryByRole("header", { name: "Do it." })).toBeNull();
  });

  // B2 (2026-11-27 review): "C# fast" and "F# a bit" drew as two large headings.
  it.each([
    ["C# and F#", "How do I learn C# fast? I know Java and F# a bit."],
    ["a sharp key", "The piece is in A# minor."],
    ["a keypad key", "Then press # to confirm."],
    ["a table cell", "| Language | Use |\n| --- | --- |\n| C# | Games |\n| F# | Data |"],
    ["inline code", "Write `x = 1  # set x` and run it."],
    ["a list item", "1. C# basics\n2. F# next"],
  ])("draws no heading in a reply for %s", async (_name, content) => {
    await render(<MarkdownContent content={content} />);
    expect(screen.queryAllByRole("header")).toHaveLength(0);
    expect(screen.getAllByText(/[CFA]#|press #|# set x/).length).toBeGreaterThan(0);
  });

  it("still breaks a heading glued onto a finished sentence", async () => {
    await render(<MarkdownContent content={"Here is the plan. ## Next steps\n\nDo it."} />);
    expect(screen.getByRole("header", { name: "Next steps" })).toBeOnTheScreen();
  });

  it("leaves a heading that holds a link open, so the link can still be focused", async () => {
    await render(<MarkdownContent content={"## [Docs](https://example.com)\n\nEnd."} />);

    expect(screen.queryAllByRole("header")).toHaveLength(0);
    expect(screen.getAllByRole("link")).toHaveLength(1);
  });
});
