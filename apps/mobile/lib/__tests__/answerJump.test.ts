import { answerJumpFor } from "@/lib/markdown/answerJump";

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

describe("the answer line a worked reply opens with", () => {
  it("names every card's value when the first card sits under the working", () => {
    expect(answerJumpFor(WORKED)).toEqual({
      values: [
        { text: String.raw`11.5\,\mathrm{m}`, notation: "math" },
        { text: String.raw`3.06\,\mathrm{s}`, notation: "math" },
      ],
    });
  });

  it("is the same for every subject: a chemistry card's value stays its text", () => {
    const reply = WORKED.replace(String.raw`11.5\,\mathrm{m}`, "2H2 + O2 -> 2H2O").replace(
      "part: a",
      "part: a\nnotation: chemistry",
    );
    expect(answerJumpFor(reply)?.values[0]).toEqual({ text: "2H2 + O2 -> 2H2O", notation: "chemistry" });
  });

  it("counts a picture above the card as working", () => {
    const reply = ["Here is the graph.", "```graph", "{}", "```", "It crosses at 1 and 3.", "```answer", "x = 1, x = 3", "```"].join("\n");
    expect(answerJumpFor(reply)?.values).toEqual([{ text: "x = 1, x = 3", notation: "math" }]);
  });

  it.each([
    ["a short reply, whose card is already in view", "The roots are:\n\n```answer\nverified: true\nx = 1, x = 3\n```"],
    ["a reply with no card", "Just some words.\n".repeat(12)],
    ["a card still streaming", `${WORKED.split("**Answer (a)**")[0]}**Answer**\n\`\`\`answer\nverified: true\n11.5`],
  ])("draws none for %s", (_name, reply) => {
    expect(answerJumpFor(reply)).toBeNull();
  });

  it("names the answer without a value too long for one line", () => {
    const reply = WORKED.replace(String.raw`11.5\,\mathrm{m}`, String.raw`\begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}`);
    expect(answerJumpFor(reply)).toEqual({ values: [] });
  });
});
