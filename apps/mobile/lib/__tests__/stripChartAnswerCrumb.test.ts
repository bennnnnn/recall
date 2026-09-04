import { preprocessMarkdown } from "@/lib/markdown/markdownPreprocess";
import {
  isBareNumericChartCrumb,
  stripNumericAnswerAfterChart,
} from "@/lib/markdown/stripChartAnswerCrumb";

const VEGA = `{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": { "values": [{"month":"Jan","inches":5.7}] },
  "mark": "bar"
}`;

describe("isBareNumericChartCrumb", () => {
  it("matches leftover means, not recap sentences", () => {
    expect(isBareNumericChartCrumb("3.1")).toBe(true);
    expect(isBareNumericChartCrumb("$3.1$")).toBe(true);
    expect(isBareNumericChartCrumb("**3.1**")).toBe(true);
    expect(isBareNumericChartCrumb("x = 2")).toBe(false);
    expect(isBareNumericChartCrumb("Mean rainfall is 3.1 inches.")).toBe(false);
  });
});

describe("stripNumericAnswerAfterChart", () => {
  it("drops an empty-lang fence whose body is the leftover mean", () => {
    const src = `Here's a chart.\n\n\`\`\`chart\n${VEGA}\n\`\`\`\n\n\`\`\`\n3.1\n\`\`\`\n`;
    const out = stripNumericAnswerAfterChart(src);
    expect(out).toContain("```chart");
    expect(out).not.toContain("3.1");
  });

  it("drops ```answer after a vega-lite fence", () => {
    const src = `\`\`\`vega-lite\n${VEGA}\n\`\`\`\n\n\`\`\`answer\n3.1\n\`\`\`\n`;
    expect(stripNumericAnswerAfterChart(src)).not.toContain("3.1");
  });

  it("drops a lone number line after the fence", () => {
    const src = `\`\`\`chart\n${VEGA}\n\`\`\`\n\n3.1\n`;
    expect(stripNumericAnswerAfterChart(src)).not.toContain("3.1");
  });

  it("keeps a real assignment fence after a chart", () => {
    const src = `\`\`\`chart\n${VEGA}\n\`\`\`\n\n\`\`\`answer\nx = 2\n\`\`\`\n`;
    expect(stripNumericAnswerAfterChart(src)).toContain("x = 2");
  });

  it("keeps a labelled statistic after the fence", () => {
    const src = `\`\`\`chart\n${VEGA}\n\`\`\`\n\nmean 42\n`;
    expect(stripNumericAnswerAfterChart(src)).toContain("mean 42");
    expect(isBareNumericChartCrumb("mean 42")).toBe(false);
  });

  it("keeps a recap sentence with the requested number", () => {
    const src = `\`\`\`chart\n${VEGA}\n\`\`\`\n\nThe mean is 42.\n`;
    expect(stripNumericAnswerAfterChart(src)).toContain("The mean is 42.");
  });
});

describe("preprocessMarkdown chart crumb", () => {
  it("BUG FIX regression: rainfall mean after ```chart does not stay an answer fence", () => {
    const src =
      "Here's a bar chart showing Seattle's average monthly rainfall!\n\n" +
      "```chart\n" +
      VEGA +
      "\n```\n\n```\n3.1\n```\n";
    const out = preprocessMarkdown(src);
    expect(out).toMatch(/```(?:chart|vega-lite)/);
    expect(out).not.toMatch(/```(?:answer)?\s*\n3\.1\s*\n```/);
    expect(out.trim().endsWith("3.1")).toBe(false);
  });
});
