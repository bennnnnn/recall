// A worked answer put its card three screens down, under Given, Required and every formula
// (2026-11-06). The reply now opens with the answer in bold, and a tap scrolls to the card.
import { StyleSheet } from "react-native";
import { fireEvent, render, within } from "@testing-library/react-native";

import { ReplyMarkdown } from "@/components/markdown/ReplyMarkdown";
import { ScrollToViewProvider } from "@/components/rich/answerJump";

jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: "LinkPreviewCard" }));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  writeAsStringAsync: jest.fn(),
  EncodingType: { UTF8: "utf8" },
}));
jest.mock("@/components/WebPreviewCodeBlock", () => ({ WebPreviewCodeBlock: "WebPreviewCodeBlock" }));
jest.mock("@/components/rich/CircularClockBlock", () => ({ CircularClockBlock: "CircularClockBlock" }));

const WORKED = [
  "**Given**  ",
  String.raw`$v_0 = 15\,\mathrm{m/s}$ (upward)  `,
  String.raw`$g = 9.8\,\mathrm{m/s^2}$`,
  "",
  "**Required**  ",
  String.raw`$h_{max}$ (maximum height)  `,
  "$t$ (time to the top)",
  "",
  "**Solution**",
  "",
  "**Maximum height formula**  ",
  String.raw`$h_{max} = \frac{v_0^2}{2g}$`,
  "",
  "**Substitution**  ",
  String.raw`$h_{max} = \frac{15^2}{2 \times 9.8}$`,
  "",
  "**Answer (a)**",
  "```answer",
  "verified: true",
  "part: a",
  String.raw`11.5\,\mathrm{m}`,
  "```",
  "",
  "**Answer (b)**",
  "```answer",
  "verified: true",
  "part: b",
  String.raw`3.06\,\mathrm{s}`,
  "```",
].join("\n");

function reply(content: string, streaming = false) {
  return <ReplyMarkdown content={content} streaming={streaming} presented userText={null} sources={[]} />;
}

describe("the answer line at the top of a worked reply", () => {
  it("opens the reply with the answers, and scrolls to the first card on a tap", async () => {
    const scrollTo = jest.fn();
    const view = await render(<ScrollToViewProvider scrollTo={scrollTo}>{reply(WORKED)}</ScrollToViewProvider>);
    const chip = view.getByTestId("answer-jump");
    // "11.5 m · 3.06 s" in bold, as a model opens with "**x = 3**": no label, no chevron
    // (November 2026). Keys stand for copy here.
    expect(chip).toHaveTextContent(/^11\.5 m·3\.06 s$/);
    for (const value of within(chip).getAllByText(/^(11\.5 m|3\.06 s)$/)) {
      expect(StyleSheet.flatten(value.props.style).fontWeight).toBe("700");
    }
    expect(chip.props.accessibilityRole).toBe("button");
    expect(chip.props.accessibilityLabel).toBe("rich.answer_a11y");
    expect(chip.props.accessibilityHint).toBe("rich.answer_jump_hint");
    // It is the first thing in the reply, above Given.
    const order = view.toJSON();
    expect(JSON.stringify(order).indexOf("answer-jump")).toBeLessThan(JSON.stringify(order).indexOf("Given"));
    await fireEvent.press(chip);
    expect(scrollTo).toHaveBeenCalledTimes(1);
    // It leads to a card's frame: the view the chat measures and scrolls to.
    const target = scrollTo.mock.calls[0][0] as { measureLayout?: unknown };
    expect(typeof target.measureLayout).toBe("function");
    expect(view.getAllByTestId("answer-label")).toHaveLength(2);
  });

  it("waits for the reply to settle, and is drawn only in a chat it can scroll", async () => {
    const scrollTo = jest.fn();
    const streaming = await render(<ScrollToViewProvider scrollTo={scrollTo}>{reply(WORKED, true)}</ScrollToViewProvider>);
    expect(streaming.queryByTestId("answer-jump")).toBeNull();
    const outside = await render(reply(WORKED));
    expect(outside.queryByTestId("answer-jump")).toBeNull();
  });

  it("keeps a value with structure typeset", async () => {
    const view = await render(
      <ScrollToViewProvider scrollTo={jest.fn()}>
        {reply(WORKED.replace(String.raw`11.5\,\mathrm{m}`, String.raw`\frac{1}{2}\,\mathrm{m}`))}
      </ScrollToViewProvider>,
    );
    expect(view.getByTestId("answer-jump")).toBeOnTheScreen();
    expect(view.queryByText(/frac|\\/)).toBeNull();
  });

  it("draws none for a short reply whose card is already in view", async () => {
    const view = await render(
      <ScrollToViewProvider scrollTo={jest.fn()}>
        {reply("The roots:\n\n```answer\nverified: true\nx = 1, x = 3\n```")}
      </ScrollToViewProvider>,
    );
    expect(view.queryByTestId("answer-jump")).toBeNull();
  });
});
