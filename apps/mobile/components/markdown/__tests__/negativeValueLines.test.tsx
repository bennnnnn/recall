/**
 * A value that opens a line or a list item keeps its minus sign. "$-2.5 < -0.33 < 0.75 <
 * 1.5$" alone on its line drew as a bullet and "2.5 < -0.33 < …" (the textbook run,
 * 2026-11-13): a pass that unwraps a prose bullet the model wrapped in dollars read the
 * sign as a list marker. Every list marker, and the reply settled and while it streams.
 */
import { cleanup, render } from "@testing-library/react-native";

import { MarkdownContent } from "@/components/MarkdownContent";

jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: () => null }));

/** The text a reader sees, the pieces in order: every minus written one way, no spaces (the
 * maths draws its own, and words flowing beside maths are pieces of their own). */
function seen(node: unknown): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") {
    return String(node).replace(/−/g, "-").replace(/[\s\u200b]/g, "");
  }
  if (Array.isArray(node)) return node.map(seen).join("");
  return ((node as { children?: unknown[] }).children ?? []).map(seen).join("");
}

const CASES: [string, RegExp][] = [
  ["Order:\n\n$-2.5 < -0.33 < 0.75 < 1.5$\n\nLeft to right.", /:-2\.5<-0\.33<0\.75<1\.5/],
  ["**Substitution**  \n$-\\frac{5}{2} = -2.5$  \n$-2.5 < -0.33 < 0.75 < 1.5$", /2\.5-2\.5<-0\.33/],
  ["**Steps**  \n$-x < 3$  \n$x > -3$", /Steps-x<3/],
  ["Order:\n\n- -2.5 < -0.33\n- -1 is left of 0", /:-2\.5<-0\.33-1isleft/],
  ["Order:\n\n* -2.5 < -0.33\n* -3 is less than 0", /:-2\.5<-0\.33-3isless/],
  ["Order:\n\n+ -2.5 < -0.33\n+ −4 is left of 0", /:-2\.5<-0\.33-4isleft/],
  ["Order:\n\n1. -2.5 < -0.33\n2. -5/2 is the least", /-2\.5<-0\.33.*-5\/2isthe/],
  ["Order:\n\n- $-\\frac{5}{2}$ is left of 0\n- $-0.33$ is next", /:-52isleftof0-0\.33isnext/],
];

describe("a value that opens a line keeps its minus", () => {
  it.each(CASES)("%s", async (content, shown) => {
    for (const streaming of [false, true]) {
      const screen = await render(<MarkdownContent content={content} streaming={streaming} />);
      expect(seen(screen.toJSON())).toMatch(shown);
      await cleanup();
    }
  });
});
