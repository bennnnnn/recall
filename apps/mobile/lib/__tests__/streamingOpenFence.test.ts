import {
  classifyOpenStreamTail,
  parseOpenFenceTail,
  parseOpenMathTail,
} from "@/lib/streamingOpenFence";

describe("parseOpenFenceTail", () => {
  it("splits lang and body from an open ``` fence", () => {
    expect(parseOpenFenceTail("```python\nprint(1)\nprint(2)\n")).toEqual({
      lang: "python",
      body: "print(1)\nprint(2)\n",
    });
  });

  it("handles ~~~ fences and empty bodies", () => {
    expect(parseOpenFenceTail("~~~js\n")).toEqual({ lang: "js", body: "" });
    expect(parseOpenFenceTail("```\n")).toEqual({ lang: "", body: "" });
  });

  it("rejects tails that are not an open fence opener", () => {
    expect(parseOpenFenceTail("just prose")).toBeNull();
    expect(parseOpenFenceTail("``python\nnope")).toBeNull();
  });
});

describe("parseOpenMathTail", () => {
  it("strips $$ / \\[ openers", () => {
    expect(parseOpenMathTail("$$\nx^2\n")).toBe("x^2\n");
    expect(parseOpenMathTail("$$x^2")).toBe("x^2");
    expect(parseOpenMathTail("\\[\na+b\n")).toBe("a+b\n");
  });
});

describe("classifyOpenStreamTail", () => {
  it("uses fence classification when the scan says a fence is open", () => {
    expect(
      classifyOpenStreamTail("```ts\nconst x = 1\n", {
        fenceOpen: true,
        dollarOpen: false,
        bracketDepth: 0,
      }),
    ).toEqual({ kind: "fence", lang: "ts", body: "const x = 1\n" });
  });

  it("uses math classification for open $$", () => {
    expect(
      classifyOpenStreamTail("$$\nE=mc^2\n", {
        fenceOpen: false,
        dollarOpen: true,
        bracketDepth: 0,
      }),
    ).toEqual({ kind: "math", body: "E=mc^2\n" });
  });

  it("falls back to other for prose tails", () => {
    expect(
      classifyOpenStreamTail("still typing", {
        fenceOpen: false,
        dollarOpen: false,
        bracketDepth: 0,
      }),
    ).toEqual({ kind: "other", text: "still typing" });
  });
});
