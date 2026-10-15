import { attachAnswerHeadingToFence } from "@/lib/markdown/attachAnswerHeading";
import { preprocessMarkdown } from "@/lib/markdown/preprocess";

describe("attachAnswerHeadingToFence", () => {
  it("drops a lone Answer heading above the server's checked card", () => {
    const source = [
      "**1. Divide both sides by 3**",
      "",
      "$x = 0$",
      "",
      "**Answer**",
      "",
      "```answer",
      "verified: true",
      "x = 0",
      "```",
    ].join("\n");

    expect(attachAnswerHeadingToFence(source)).toBe(
      [
        "**1. Divide both sides by 3**",
        "",
        "$x = 0$",
        "",
        "```answer",
        "verified: true",
        "x = 0",
        "```",
      ].join("\n"),
    );
  });

  it.each(["**Answer:**", "## Answer", "Answer:"])(
    "drops %s above an unmarked card too: the card draws its own heading",
    (heading) => {
      const source = `${heading}\n\n\`\`\`answer\nx = 0\n\`\`\``;
      expect(attachAnswerHeadingToFence(source)).toBe("```answer\nx = 0\n```");
    },
  );

  it("leaves Answer in place when no answer fence follows", () => {
    expect(attachAnswerHeadingToFence("**Answer**\n\nThe result is 4.")).toBe(
      "**Answer**\n\nThe result is 4.",
    );
  });
});

describe("preprocessMarkdown answer heading", () => {
  it("keeps Answer out of its own paragraph before the chip", () => {
    const source = "**Given:** $3x = 0$\n\n**Answer**\n\n```answer\nverified: true\nx = 0\n```\n";
    const out = preprocessMarkdown(source);
    expect(out).not.toMatch(/\*\*Answer\*\*/);
    expect(out).toContain("```answer\nverified: true\nx = 0\n```");
  });
});
