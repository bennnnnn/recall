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
      ["Divide both sides:", "```math", "4x = 4", "```", "", "    2. **Simplify:**", "    3. **Check:**"],
      ["**Simplify:**", "**Check:**"],
    ],
    [
      "a bullet after a margin fence ended the list",
      ["- **Subtract 3**", "```math", "2x=8", "```", "", "    - **Divide by 2:**", "    - **Check:**"],
      ["**Divide by 2:**", "**Check:**"],
    ],
    [
      "a bullet after a fence the list lift moves to the margin",
      ["- **Subtract 3**", "   ```math", "   2x=8", "   ```", "", "    - **Divide by 2:**", "    - **Check:**"],
      ["**Divide by 2:**", "**Check:**"],
    ],
  ])("lifts misindented steps after a maths fence, all of them: %s", (_name, lines, steps) => {
    const out = preprocessMarkdown(lines.join("\n"));
    const tokens = markdownItInstance.parse(out, {});
    expect(tokens.some((t) => t.type === "code_block")).toBe(false);
    // Siblings at the margin: none nested under the one lifted before it.
    const list = items(lines.join("\n"));
    expect(main(list).filter((text) => steps.includes(text.trim()))).toEqual(steps);
    expect(members(list)).toEqual([]);
  });

  it.each(["### Natural sciences", "Its main branches:", "```text\nnot a list\n```"])(
    "lifts every indented bold bullet under %s, not only the first",
    (above) => {
      const reply = [above, "", "    - **Physics**: matter and energy", "    - **Chemistry**: substances", "    - **Biology**: life"].join("\n");
      const list = items(reply);
      expect(main(list)).toEqual([
        "**Physics**: matter and energy",
        "**Chemistry**: substances",
        "**Biology**: life",
      ]);
      expect(members(list)).toEqual([]);
    },
  );

  it("keeps three numbered levels where they are, and the main numbering whole", () => {
    const reply = [
      "1. **Natural**",
      "    1. **Physics**",
      "        1. Mechanics",
      "        2. Optics",
      "    2. **Chemistry**",
      "2. **Social**",
    ].join("\n");
    const out = preprocessMarkdown(reply);
    expect(out).toContain("    2. **Chemistry**");
    const list = items(reply);
    expect(main(list)).toEqual(["**Natural**", "**Social**"]);
    expect(members(list)).toEqual(["**Physics**", "**Chemistry**"]);
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
