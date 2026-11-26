import { preprocessMarkdown } from "@/lib/markdown/preprocess";
import { markdownItInstance } from "@/lib/markdown/parser";

/**
 * The owner's shape for an informational reply (2026-11-26): a title, numbered main
 * items with bold names, and each item's members as a nested list under it. The phone's
 * step repair lifted any 4-space "1. **…**" or "- **…**" line to the margin, so members
 * left their item and the main list renumbered ("2. Social science" drew as "4.").
 */

type Item = { depth: number; ordered: boolean; text: string };

function items(markdown: string): Item[] {
  const tokens = markdownItInstance.parse(preprocessMarkdown(markdown), {});
  const out: Item[] = [];
  let depth = 0;
  const ordered: boolean[] = [];
  for (let i = 0; i < tokens.length; i += 1) {
    const token = tokens[i];
    if (token.type === "bullet_list_open" || token.type === "ordered_list_open") {
      ordered.push(token.type === "ordered_list_open");
      depth += 1;
    } else if (token.type === "bullet_list_close" || token.type === "ordered_list_close") {
      ordered.pop();
      depth -= 1;
    } else if (token.type === "list_item_open") {
      const inline = tokens.slice(i).find((t) => t.type === "inline");
      out.push({ depth, ordered: ordered[ordered.length - 1], text: inline?.content ?? "" });
    }
  }
  return out;
}

const main = (list: Item[]) => list.filter((item) => item.depth === 1).map((item) => item.text);
const members = (list: Item[]) => list.filter((item) => item.depth === 2).map((item) => item.text);

describe("an informational reply's nested members", () => {
  it.each([
    ["three spaces", "   "],
    ["four spaces", "    "],
  ])("stay under their numbered item with %s of indent", (_name, indent) => {
    const reply = [
      "Science is usually split into three groups.",
      "",
      "## Types of Science",
      "",
      "1. **Natural science** — studies the physical and living world.",
      `${indent}- **Chemistry**`,
      `${indent}- **Biology**`,
      "2. **Social science** — studies people and societies.",
      `${indent}- History`,
      `${indent}- Economics`,
    ].join("\n");
    const list = items(reply);
    expect(main(list)).toHaveLength(2);
    expect(main(list)[1]).toContain("**Social science**");
    expect(members(list)).toEqual(["**Chemistry**", "**Biology**", "History", "Economics"]);
  });

  it("keeps a nested numbered list nested, and the main numbering whole", () => {
    const reply = [
      "1. **Natural science** — the physical world.",
      "    1. Chemistry",
      "    2. Biology",
      "2. **Social science** — people and societies.",
      "    1. History",
    ].join("\n");
    const list = items(reply);
    expect(main(list)).toEqual([
      "**Natural science** — the physical world.",
      "**Social science** — people and societies.",
    ]);
    expect(members(list)).toEqual(["Chemistry", "Biology", "History"]);
  });

  it.each([
    [
      "a numbered step with no list open",
      ["Divide both sides:", "```math", "4x = 4", "```", "", "    2. **Simplify:**"],
      "**Simplify:**",
    ],
    [
      "a bullet after a margin fence ended the list",
      ["- **Subtract 3**", "```math", "2x=8", "```", "", "    - **Divide by 2:**", "    - **Check:**"],
      "**Divide by 2:**",
    ],
    [
      "a bullet after a fence the list lift moves to the margin",
      ["- **Subtract 3**", "   ```math", "   2x=8", "   ```", "", "    - **Divide by 2:**", "    - **Check:**"],
      "**Divide by 2:**",
    ],
  ])("lifts a misindented step after a maths fence: %s", (_name, lines, step) => {
    const out = preprocessMarkdown(lines.join("\n"));
    const tokens = markdownItInstance.parse(out, {});
    expect(tokens.some((t) => t.type === "code_block")).toBe(false);
    expect(out).toContain(step);
    // Every lifted step is a sibling at the margin, none nested under the first.
    expect(members(items(lines.join("\n")))).toEqual([]);
  });

  it("lifts every sibling of a misindented bullet after a heading, not only the first", () => {
    const reply = [
      "### Natural sciences",
      "    - **Physics**: matter",
      "    - **Chemistry**: substances",
      "    - **Biology**: life",
    ].join("\n");
    const list = items(reply);
    expect(main(list)).toEqual([
      "**Physics**: matter",
      "**Chemistry**: substances",
      "**Biology**: life",
    ]);
    expect(members(list)).toEqual([]);
  });

  it("still lifts a misindented next step to the margin", () => {
    const reply = ["1. **Divide both sides by 4**", "", "    2. **Simplify:**", "", "x = 1"].join(
      "\n",
    );
    const list = items(reply);
    expect(main(list).map((text) => text.replace(/\s+$/, ""))).toEqual([
      "**Divide both sides by 4**",
      "**Simplify:**",
    ]);
  });
});
