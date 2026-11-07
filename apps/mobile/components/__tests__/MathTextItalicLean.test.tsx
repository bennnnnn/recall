import type { ReactElement } from "react";
import { Dimensions, StyleSheet } from "react-native";
import { render } from "@testing-library/react-native";
import type { JsonNode } from "test-renderer";

import { MathText } from "@/components/rich/MathText";
import { endsOnItalicLetter, ITALIC_LEAN_EM } from "@/components/rich/mathText/runs";
import { MathDraftPreview } from "@/features/chat/components/MathDraftPreview";

const LEAN = ITALIC_LEAN_EM * 16;

/** The right padding of every Text drawn, in tree order. */
async function padsOf(element: ReactElement): Promise<number[]> {
  const screen = await render(element);
  const pads: number[] = [];
  const walk = (node: JsonNode | null) => {
    if (!node || typeof node === "string") return;
    if (node.type === "Text") {
      const pad = StyleSheet.flatten(node.props.style)?.paddingRight;
      pads.push(typeof pad === "number" ? pad : 0);
    }
    node.children?.forEach(walk);
  };
  const tree = screen.toJSON();
  (Array.isArray(tree) ? tree : [tree]).forEach(walk);
  return pads;
}

const rightPads = (latex: string, lean = true) => padsOf(<MathText latex={latex} lean={lean} />);
const draftPads = (input: string) => padsOf(<MathDraftPreview input={input} showCaret={false} />);

beforeEach(() => {
  jest.spyOn(Dimensions, "get").mockReturnValue({ width: 390, height: 844, scale: 3, fontScale: 1 });
});

afterEach(() => jest.restoreAllMocks());

describe("MathText italic lean", () => {
  it.each([
    ["P", true],
    ["x+V", true],
    ["Φ", true],
    ["x^{2}", false],
    ["5", false],
    [String.raw`\sin`, false],
    ["P ", false],
  ])("reads whether %j ends on an italic letter", (value, italic) => {
    expect(endsOnItalicLetter(value)).toBe(italic);
  });

  it("draws a reply's maths with no lean: only a host that asks gets one", async () => {
    expect(await padsOf(<MathText latex="P" />)).not.toContain(LEAN);
    expect(await padsOf(<MathText latex={String.raw`\frac{1}{2}P`} />)).not.toContain(LEAN);
  });

  it("gives a formula that ends on an italic letter room to lean into", async () => {
    // `P` alone in the composer drew as `F`: its bowl leaned out of the box.
    expect(await rightPads("P")).toContain(LEAN);
    expect(await rightPads(String.raw`P(5,2) = 20\,V`)).toContain(LEAN);
  });

  it("leans the last run of a formula with stacked parts", async () => {
    const pads = await rightPads(String.raw`\frac{1}{2}P`);
    expect(pads.filter((pad) => pad === LEAN)).toHaveLength(1);
  });

  it.each(["x^{2}", "5", String.raw`\sin(x)`, String.raw`3\,\mathrm{kg}`])(
    "adds no room after %s, which does not end on an italic letter",
    async (latex) => {
      expect(await rightPads(latex)).not.toContain(LEAN);
    },
  );

  it.each([
    "x_{i}^{2}",
    String.raw`\frac{1}{2}mv_{0}^{2}`,
    "x_1^2 + x_2^2",
    // The script column is a box inside the formula, not its end: neither T nor x leans.
    String.raw`T_{1}^{\frac{1}{2}x}`,
  ])("sets the scripts of %s right against their base", async (latex) => {
    expect(await rightPads(latex)).toEqual(await rightPads(latex, false));
  });
});

describe("the composer's italic lean", () => {
  it.each(["$P(5,2)$", "$x+P$", "Solve $P$ now"])("leans a letter that ends a piece of %s", async (input) => {
    expect(await draftPads(input)).toContain(LEAN);
  });

  it.each(["$x^{2}$", "$x_{1}$", "$a_{n}$", "$2x^{2}$"])("sets the script of %s against its letter", async (input) => {
    expect(await draftPads(input)).not.toContain(LEAN);
  });

  it.each(["$x^{n}$", String.raw`$\frac{x}{y}$`, String.raw`$\sqrt{P}$`, String.raw`$\frac{x^{2}}{y}$`, "$(x)$"])(
    "leans no letter inside a box of %s",
    async (input) => {
      expect(await draftPads(input)).not.toContain(LEAN);
    },
  );
});
