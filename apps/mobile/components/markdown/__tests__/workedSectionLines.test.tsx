/**
 * A worked reply a model wrote itself, drawn as the server's (the textbook run, 2026-11-13).
 * Written with single line breaks ("$3x - 5 < 2x + 4$" then "**Required**"), its sections
 * ran into one paragraph: "3x − 5 < 2x + 4 **Required** Solve for x. **Solution**" and
 * "A = 2B + Ph **Substitution**". Each heading now starts its own section, settled and while
 * it streams, and a bold label in a sentence stays on its line.
 */
import { cleanup, render, within } from "@testing-library/react-native";

import { MarkdownContent } from "@/components/MarkdownContent";

jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: () => null }));

/** The text a reader sees, the pieces in order. */
function seen(node: unknown): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(seen).join("");
  return ((node as { children?: unknown[] }).children ?? []).map(seen).join("");
}

// The saved b12 and b27 replies (GPT-6 Luna, 2026-11-13), and look-alikes a model writes:
// a section title with words after it, a part, a numbered move with ")".
const INEQUALITY = [
  "### Solve the inequality",
  "**Given**  ",
  "$3x - 5 < 2x + 4$",
  "**Required**  ",
  "Solve for $x$.",
  "**Solution**",
  "",
  "**1. Subtract $2x$ from both sides** — Subtraction property of inequality",
  "$x - 5 < 4$",
  "**2. Add $5$ to both sides** — Addition property of inequality",
  "$x < 9$",
].join("\n");
const PRISM = [
  "**Given**  ",
  "Prism altitude: $15\\ \\text{cm}$  ",
  "Base area: $24\\ \\text{cm}^2$  ",
  "**Required**  ",
  "Total surface area",
  "**Solution**  ",
  "",
  "**Total surface area formula**  ",
  "$A = 2B + Ph$",
  "**Substitution**  ",
  "$A = 2(24) + 24(15)$",
  "$A = 48 + 360$",
  "**Answer**  ",
  "$\\boxed{408\\ \\text{cm}^2}$",
].join("\n");
const TITLES = [
  "**Given**  ",
  "$m = 2\\,\\mathrm{kg}$, $a = 3\\,\\mathrm{m/s^2}$",
  "**Required:** the force $F$",
  "**(a) Force on the cart**",
  "$F = m a$",
  "**Answer (a)**  ",
  "$F = 6\\,\\mathrm{N}$",
].join("\n");

async function headings(content: string, streaming: boolean): Promise<string[]> {
  const screen = await render(<MarkdownContent content={content} streaming={streaming} />);
  const found = [
    ...screen.queryAllByTestId("workout-heading"),
    ...screen.queryAllByTestId("workout-subheading"),
    ...screen.queryAllByTestId("lesson-step-label"),
    ...screen.queryAllByTestId("workout-part-title"),
  ].map((node) => seen(node.children).trim());
  // No heading's word is left inside a line of working.
  const lines = screen.queryAllByTestId("workout-line").map((node) => seen(node.children));
  expect(lines.filter((line) => /Required|Solution|Substitution|Answer/.test(line))).toEqual([]);
  await cleanup();
  return found;
}

describe("a worked reply written with single line breaks", () => {
  it.each([false, true])("starts each section on its own line (streaming: %s)", async (streaming) => {
    expect(await headings(INEQUALITY, streaming)).toEqual(
      expect.arrayContaining(["Given", "Required", "Solution", "Subtract 2x from both sides", "Add 5 to both sides"]),
    );
    expect(await headings(PRISM, streaming)).toEqual(
      expect.arrayContaining(["Given", "Required", "Solution", "Total surface area formula", "Substitution", "Answer"]),
    );
  });

  it("keeps each line of working its own row", async () => {
    const screen = await render(<MarkdownContent content={PRISM} />);
    const substitution = screen.getAllByTestId("workout-section").find((node) =>
      seen(node.children).startsWith("Substitution"),
    )!;
    expect(within(substitution).getAllByTestId("workout-line")).toHaveLength(2);
    await cleanup();
  });

  it("starts a section title with words after it and a part on their own lines", async () => {
    const screen = await render(<MarkdownContent content={TITLES} />);
    const given = seen(screen.getAllByTestId("workout-section")[0]!.children);
    expect(given).toMatch(/^Given/);
    expect(given).not.toMatch(/Required/);
    expect(screen.getByTestId("workout-part")).toBeOnTheScreen();
    expect(screen.getByTestId("workout-answer")).toHaveTextContent(/F = 6/);
    await cleanup();
  });

  it("leaves a bold label in a sentence and an unworked reply as written", async () => {
    const label = "**Given**  \n$m = 5\\,\\mathrm{kg}$  \n**Speed:** $3\\,\\mathrm{m/s}$";
    const screen = await render(<MarkdownContent content={label} />);
    expect(seen(screen.toJSON())).toMatch(/Speed:/);
    expect(screen.queryAllByTestId("workout-subheading")).toHaveLength(0);
    await cleanup();
    const plan = await render(<MarkdownContent content={"Here is the plan:\n**Step 1** boil the water."} />);
    expect(seen(plan.toJSON())).toMatch(/Here is the plan: Step 1 boil the water\./);
    await cleanup();
  });
});
