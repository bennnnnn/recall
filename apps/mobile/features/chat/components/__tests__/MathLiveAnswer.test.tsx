import { render } from "@testing-library/react-native";

import { MathLiveAnswer } from "@/features/chat/components/MathLiveAnswer";

type Node = { children: (Node | string)[] };
const text = (node: Node | string): string =>
  typeof node === "string" ? node : node.children.map(text).join("");

async function shown(input: string): Promise<string> {
  const { getByTestId } = await render(<MathLiveAnswer input={input} />);
  // MathText spaces with a thin space; read it as a plain one.
  return text(getByTestId("math-live-answer") as unknown as Node).replace(/\s+/g, " ");
}

describe("MathLiveAnswer", () => {
  it("writes out the branches of a ± draft that fits its row", async () => {
    expect(await shown("$2\\pm 1$")).toContain("2− 1 = 1, 2+ 1 = 3");
    // A fraction in each branch is no taller than a fraction answer.
    expect(await shown("$\\frac{-3\\pm\\sqrt{9-8}}{2}$")).toContain("= −2,");
  });

  it("shows only the values when the branches would be taller than the row", async () => {
    // A fraction in a fraction, echoed in each branch, is taller than the row holds.
    expect(await shown("$\\frac{1}{1+\\frac{1}{2}}\\pm 1$")).toContain("= −13, 53");
  });
});
