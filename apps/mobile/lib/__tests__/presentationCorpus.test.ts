import { preprocessMarkdown } from "@/lib/markdown/preprocess";
import { preprocessMarkdownForStream } from "@/lib/markdown/preprocessStream";
import { presentAssistantMarkdown, presentStreamTail } from "@/lib/markdown/presentation";
import { splitMathExpression } from "@/lib/markdown/calculationLayout";

const TRAIN = "A train travels at**60 km/h** and returns at**40 km/h**.";
const CYCLIST = "A cyclist rides **12 km** at**20 km/h**, then**8 km** at**10 km/h**.";
const ANSWER = "The answer is **48 km/h** — not **50 km/h**.";

describe("presentation corpus", () => {
  it("separates glued bold values", () => {
    const train = presentAssistantMarkdown(TRAIN);
    const cyclist = presentAssistantMarkdown(CYCLIST);
    expect(train).toContain("at **60 km/h**");
    expect(train).toContain("at **40 km/h**");
    expect(train).not.toContain("at**");
    expect(cyclist).toContain("at **20 km/h**");
    expect(cyclist).toContain("then **8 km**");
    expect(cyclist).toContain("at **10 km/h**");
    expect(cyclist).not.toContain("then**");
    expect(cyclist).not.toContain("at**");
  });

  it("keeps punctuation, code, links, and inline math boundaries", () => {
    expect(presentAssistantMarkdown(ANSWER)).toBe(ANSWER);
    expect(presentAssistantMarkdown("(**important**)")).toBe("(**important**)");
    expect(presentAssistantMarkdown("Use `yield` when appropriate.")).toBe(
      "Use `yield` when appropriate.",
    );
    expect(presentAssistantMarkdown("Use`yield`when appropriate.")).toBe(
      "Use `yield` when appropriate.",
    );
    expect(presentAssistantMarkdown("See [the documentation](https://example.com/docs).")).toBe(
      "See [the documentation](https://example.com/docs).",
    );
    expect(presentAssistantMarkdown("See[the documentation](https://example.com/docs)now")).toBe(
      "See [the documentation](https://example.com/docs) now",
    );
    expect(presentAssistantMarkdown("speed is $v=5$ km/h")).toBe("speed is $v=5$ km/h");
    expect(presentAssistantMarkdown("speed is$v=5$km/h")).toBe("speed is $v=5$ km/h");
  });

  it("leaves unclosed tokens, urls, code, quotes, and CJK alone", () => {
    expect(presentAssistantMarkdown("at**40")).toBe("at**40");
    expect(presentAssistantMarkdown("speed is $v = 5")).toBe("speed is $v = 5");
    expect(presentAssistantMarkdown("see https://example.com/a**b** now")).toBe(
      "see https://example.com/a**b** now",
    );
    expect(presentAssistantMarkdown("```python\nprint('at**40**')\n```")).toBe(
      "```python\nprint('at**40**')\n```",
    );
    expect(presentAssistantMarkdown("> at**40 km/h**")).toBe("> at**40 km/h**");
    expect(presentAssistantMarkdown("速度**40**米")).toBe("速度**40**米");
    expect(presentAssistantMarkdown("2*3*4")).toBe("2*3*4");
    expect(presentAssistantMarkdown("It costs $5 and $10.")).toBe("It costs $5 and $10.");
  });

  it("splits reasoning chains and keeps atomic formulas", () => {
    expect(presentAssistantMarkdown("$v = d/t = 50/10 = 5$")).toBe(
      "$v = d/t$  \n$v = 50/10$  \n$v = 5$",
    );
    expect(presentAssistantMarkdown("$t_1=d/60,\\quad t_2=d/40$")).toBe(
      "$t_1=d/60$  \n$t_2=d/40$",
    );
    expect(
      splitMathExpression("t_{\\text{total}} = d/60 + d/40 = (2d+3d)/120 = 5d/120"),
    ).toEqual([
      "t_{\\text{total}} = d/60 + d/40",
      "t_{\\text{total}} = (2d+3d)/120",
      "t_{\\text{total}} = 5d/120",
    ]);
    expect(presentAssistantMarkdown("$12 + 8 = 20\\text{ km}$")).toBe("$12 + 8 = 20\\text{ km}$");
    expect(presentAssistantMarkdown("$x = 2 or x = -2$")).toBe("$x = 2 or x = -2$");
    expect(presentAssistantMarkdown("$2x - 1 = 0 \\rightarrow x = 1/2$")).toBe(
      "$2x - 1 = 0 \\rightarrow x = 1/2$",
    );
    const quadratic = "$x = \\frac{-b\\pm\\sqrt{b^2-4ac}}{2a}$";
    expect(presentAssistantMarkdown(quadratic)).toBe(quadratic);
    expect(presentAssistantMarkdown("$4! = 4 \\times 3 \\times 2 \\times 1 = 24$")).toBe(
      "$4! = 4 \\times 3 \\times 2 \\times 1 = 24$",
    );
    expect(splitMathExpression("f(x, y) = 1")).toBeNull();
    expect(presentAssistantMarkdown("n = m/M = 10/18")).toBe("$n = m/M$  \n$n = 10/18$");
    expect(presentAssistantMarkdown("Atoms of each element in water = 2")).toBe(
      "Atoms of each element in water = 2",
    );
  });

  it("matches streaming and final output for closed prose and calculation rows", () => {
    const parenChain = "  \\(\n  v = d/t = 50/10 = 5\n  \\)";
    for (const source of [TRAIN, CYCLIST, ANSWER, "$v = d/t = 50/10 = 5$\n", parenChain]) {
      const streamed = preprocessMarkdownForStream(source, null).prepared;
      expect(streamed).toBe(preprocessMarkdown(source));
    }
    const partial = preprocessMarkdownForStream("at**40", null).prepared;
    expect(partial).toBe("at**40");
    expect(partial).toBe(presentAssistantMarkdown("at**40"));
  });

  it("wraps a bare fraction on the streaming tail and leaves an open fence alone", () => {
    const wrapped = presentStreamTail(String.raw`half is \frac{1}{2}`);
    expect(wrapped).toContain(String.raw`$\frac{1}{2}$`);
    expect(wrapped).not.toMatch(/(?:^|[^$])\\frac/);
    const openFence = presentStreamTail(String.raw`see` + "\n```\n\\frac{1}{2}\n");
    expect(openFence.startsWith("see")).toBe(true);
    expect(openFence).toContain("```\n\\frac{1}{2}\n");
    expect(openFence).not.toContain("$\\frac");
    expect(preprocessMarkdownForStream(String.raw`half is \frac{1}{2}`, null).prepared).toBe(wrapped);
  });

  it("keeps units, signs, statistics, and adjacent tokens readable", () => {
    expect(presentAssistantMarkdown("**speed**$v=5$")).toBe("**speed** $v=5$");
    expect(presentAssistantMarkdown("about**12%**of the sample")).toBe("about **12%** of the sample");
    expect(presentAssistantMarkdown("dropped to$-5$ overnight")).toBe("dropped to $-5$ overnight");
    const scientific = "$N = 6.02 \\times 10^{23}$";
    expect(presentAssistantMarkdown(scientific)).toBe(scientific);
    const statistic = "$s = \\sqrt{\\frac{\\sum (x-\\bar x)^2}{n-1}}$";
    expect(presentAssistantMarkdown(statistic)).toBe(statistic);
    expect(presentAssistantMarkdown("$1\\text{ km} = 1000\\text{ m} = 100000\\text{ cm}$")).toBe(
      "$1\\text{ km} = 1000\\text{ m}$  \n$1\\text{ km} = 100000\\text{ cm}$",
    );
    expect(presentAssistantMarkdown("$n = \\frac{m}{M} = \\frac{10}{18}$")).toBe(
      "$n = \\frac{m}{M}$  \n$n = \\frac{10}{18}$",
    );
    const table = "| $v = d/t = 5$ | **48 km/h** |";
    expect(presentAssistantMarkdown(table)).toBe(table);
    expect(presentAssistantMarkdown("- rides **12 km** at**20 km/h**")).toBe(
      "- rides **12 km** at **20 km/h**",
    );
  });

  it("is idempotent", () => {
    const source = `${CYCLIST}\n\n$v = d/t = 50/10 = 5$`;
    const once = presentAssistantMarkdown(source);
    expect(presentAssistantMarkdown(once)).toBe(once);
  });
});
