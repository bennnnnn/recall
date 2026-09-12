import { hasIncompleteStreamingLatex, prepareStreamingMathText } from "@/lib/math/streamingMath";
import { splitInlineMath } from "@/lib/markdown/inlineMath";
import { parseSimpleLatex, restoreMathEscapes, segmentsToPlain } from "@/lib/mathText";

describe("streaming math preview", () => {
  it.each([String.raw`\fr`, String.raw`\frac{1}`, String.raw`\frac{1}{`, String.raw`\sqrt{3`, String.raw`\begin{cases}x`])(
    "holds incomplete syntax without inventing a finished answer: %s", (body) => {
      expect(hasIncompleteStreamingLatex(body)).toBe(true);
    },
  );
  it.each([String.raw`\frac{1}{2}`, String.raw`\sqrt[3]{3}`, String.raw`\int_0^1 x^2\,dx`])(
    "allows a complete math preview: %s", (body) => {
      expect(hasIncompleteStreamingLatex(body)).toBe(false);
    },
  );
  it.each(["$\\", String.raw`$\fr`, String.raw`$x^`, String.raw`\(\frac{1}`, String.raw`\[\int_0^1`, String.raw`$$\sqrt{3`])(
    "retains preceding prose while an explicit math span is open: %s", (formula) => {
      expect(prepareStreamingMathText(`Result: ${formula}`)).toEqual({ text: "Result: ", pending: true });
    },
  );
  it("protects a just-closed formula before the line-ending token arrives", () => {
    const result = prepareStreamingMathText(String.raw`Thus \(x_1 * x_2 = \frac{1}{2}\).`);
    expect(result.pending).toBe(false);
    const math = splitInlineMath(result.text).find((part) => part.type === "math");
    expect(segmentsToPlain(parseSimpleLatex(math!.value))).toBe("x_1 * x_2 = 1/2");
  });
  it.each([
    String.raw`\int_0^1 x^2\,dx=\frac{1}{3}`,
    String.raw`\text{force}=\frac{m}{s}`,
  ])("keeps multiple protected commands classified as math: %s", (formula) => {
    const result = prepareStreamingMathText(`Result: $${formula}$`);
    const math = splitInlineMath(result.text).filter((part) => part.type === "math");
    expect(math).toHaveLength(1);
    expect(restoreMathEscapes(math[0].value)).toBe(formula);
    expect(result.pending).toBe(false);
  });
  it.each(["Price: $5 and $10.", "It costs $5 for x^2 copies", String.raw`Price: \$5`, "Budget: ($$)", 'Type `$\\frac` in LaTeX.']) (
    "preserves code and currency: %s", (text) => {
      expect(prepareStreamingMathText(text)).toEqual({ text, pending: false });
    },
  );
});
