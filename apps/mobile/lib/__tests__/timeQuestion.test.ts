import {
  assistantReplyIsTimeAnswer,
  isRemoteTimeQuestion,
  isTimeQuestion,
} from "@/lib/timeQuestion";

describe("timeQuestion", () => {
  it("treats shorthand local asks as time questions", () => {
    expect(isTimeQuestion("What time")).toBe(true);
    expect(isTimeQuestion("what time is it")).toBe(true);
  });

  it("does not treat city asks as local time questions", () => {
    expect(isTimeQuestion("What time is it in dc")).toBe(false);
    expect(isRemoteTimeQuestion("What time is it in dc")).toBe(true);
    expect(isRemoteTimeQuestion("time in Tokyo")).toBe(true);
  });

  it("only shows the clock widget for city asks when a timezone is pinned", () => {
    expect(
      assistantReplyIsTimeAnswer("```clock\n```", "What time is it in dc"),
    ).toBe(false);
    expect(
      assistantReplyIsTimeAnswer(
        "```clock\nAmerica/New_York\n```",
        "What time is it in dc",
      ),
    ).toBe(true);
    expect(assistantReplyIsTimeAnswer("```clock\n```", "What time is it")).toBe(
      true,
    );
  });
});
