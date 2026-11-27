/**
 * The owner's layout for an informational reply (#2601): numbered main items, each a
 * **bold name**, a dash and a sentence or two, its members nested under it. The name
 * stays inline with its text, which wraps under it, for every item of a list: a short
 * description or a long one, with an emoji in front or none, while it streams and once it
 * settles. Before (review H10, 2026-11-27), a long description put its name on a line of
 * its own and a bold number beside it, a short one or an emoji-led one did not, and only
 * once its line had ended: siblings drew three ways and each item jumped as its line
 * finished, with "**" showing while a name was typed.
 */
import { render, type RenderResult } from "@testing-library/react-native";
import { StyleSheet, type StyleProp, type TextStyle } from "react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { STREAM_CARET } from "@/components/StreamingCursor";
import { streamReply } from "@/lib/__tests__/support/streamBench";
import { markdownItInstance } from "@/lib/markdown/parser";

jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: "LinkPreviewCard" }));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  writeAsStringAsync: jest.fn(),
  EncodingType: { UTF8: "utf8" },
}));

type Json = { type: string; props: { style?: StyleProp<TextStyle> }; children: (Json | string)[] | null };

/** The streaming caret's mark, and the bar it draws as inside a line. */
const CARETS = [STREAM_CARET, "▏"];

/** The text a node draws, the caret left out. */
function textOf(node: Json | string): string {
  if (typeof node === "string") return CARETS.reduce((text, caret) => text.split(caret).join(""), node);
  return (node.children ?? []).map(textOf).join("");
}

function firstText(node: Json): Json | null {
  for (const child of node.children ?? []) {
    if (typeof child === "string") continue;
    if (child.type === "Text") return child;
    const found = firstText(child);
    if (found) return found;
  }
  return null;
}

type ItemShape = { number: string; weight: unknown; firstRun: string };

/** Each numbered item as drawn: its number's weight and the first run of its text. */
function numberedItems(view: RenderResult): ItemShape[] {
  const out: ItemShape[] = [];
  const walk = (node: Json | string | null) => {
    if (!node || typeof node === "string") return;
    const [head, body] = node.children ?? [];
    if (
      node.type === "View" &&
      head && typeof head !== "string" && head.type === "Text" &&
      /^\d+\.$/.test(textOf(head)) &&
      body && typeof body !== "string"
    ) {
      const run = firstText(body);
      out.push({
        number: textOf(head),
        weight: StyleSheet.flatten(head.props.style)?.fontWeight,
        firstRun: run ? textOf(run) : "",
      });
    }
    (node.children ?? []).forEach(walk);
  };
  const tree = view.toJSON() as Json | Json[] | null;
  (Array.isArray(tree) ? tree : [tree]).forEach(walk);
  return out;
}

function allText(view: RenderResult): string {
  const tree = view.toJSON() as Json | Json[] | null;
  return (Array.isArray(tree) ? tree : [tree]).map((node) => (node ? textOf(node) : "")).join("");
}

const ITEMS = [
  ["**Democracy**", "power rests with the people, who vote for their leaders."],
  ["**Monarchy**", "a king or queen rules."],
  ["🏛️ **Republic**", "the head of state is elected, not born to the role, for a fixed term."],
  ["👑 **Oligarchy**", "a few rule."],
  ["**Theocracy:**", "religious leaders rule, as in Vatican City."],
] as const;

const REPLY = [
  "Governments differ in **who holds power**.",
  "",
  "## Types of Government",
  "",
  ...ITEMS.flatMap(([name, text], index) => [
    `${index + 1}. ${name} — ${text}`,
    ...(index === 0 ? ["    - **Direct**: citizens vote on laws", "    - **Representative**: they elect others"] : []),
  ]),
  "",
].join("\n");

/** What each item draws once whole: the name and its text on one run. */
const WHOLE = ITEMS.map(([name, text]) => `${name.replace(/\*\*/g, "")} — ${text}`);

async function shapes(content: string, streaming: boolean): Promise<ItemShape[]> {
  const view = await render(<MarkdownContent content={content} streaming={streaming} />);
  const items = numberedItems(view);
  await view.unmount();
  return items;
}

describe("a list's main items draw alike", () => {
  it.each([false, true])("settled and streamed whole (streaming %s): name inline, number regular", async (streaming) => {
    const items = await shapes(REPLY, streaming);
    expect(items.map((item) => item.firstRun)).toEqual(WHOLE);
    expect(new Set(items.map((item) => item.weight)).size).toBe(1);
    for (const item of items) {
      expect(item.firstRun).not.toContain("\n");
      expect(item.weight).not.toBe("700");
    }
  });

  it("draws an item the same while its line types and once it ends: nothing reflows", async () => {
    const settled = await shapes(REPLY, false);
    // Every flush that ends inside a main item's text, after its name has closed.
    const lines = REPLY.split("\n");
    let offset = 0;
    for (const line of lines) {
      const item = /^(\d+)\. /.exec(line);
      const dash = line.indexOf(" — ");
      if (item && dash > 0) {
        const index = Number(item[1]) - 1;
        for (let end = dash + 4; end <= line.length; end += 5) {
          const streamed = await shapes(REPLY.slice(0, offset + end), true);
          const live = streamed[index]!;
          // The run so far is the start of the settled run: same place, same weight.
          expect(settled[index]!.firstRun.startsWith(live.firstRun.trimEnd())).toBe(true);
          expect(live.weight).toBe(settled[index]!.weight);
          // The items above are drawn as they settle.
          expect(streamed.slice(0, index)).toEqual(settled.slice(0, index));
        }
      }
      offset += line.length + 1;
    }
  });

  // Every flush of the stream, one character at a time, as the row's pipeline draws it.
  // Rendering each of them (~450 screens) took 2.6 s here and passed 5 s on CI's slower
  // runner (review round 2, 2026-11-27); markdown-it reads the same pieces the screen draws.
  it("never shows an asterisk at any point of the stream", () => {
    streamReply(REPLY, 1, undefined, (pieces, sent) => {
      const text = pieces.map(plainText).join("");
      if (text.includes("*")) throw new Error(`"*" drawn after ${JSON.stringify(sent)}: ${text}`);
    });
  });

  it("never shows an asterisk on screen while a name is typed", async () => {
    for (let end = 1; end <= REPLY.length; end += 9) {
      const view = await render(<MarkdownContent content={REPLY.slice(0, end)} streaming />);
      const drawn = allText(view);
      await view.unmount();
      if (drawn.includes("*")) throw new Error(`"*" drawn at ${end}: ${JSON.stringify(REPLY.slice(0, end))}`);
    }
  }, 30_000);
});

/** The text markdown-it draws for a piece, its code left out. */
function plainText(markdown: string): string {
  return markdownItInstance
    .parse(markdown, {})
    .filter((token) => token.type === "inline")
    .flatMap((token) => token.children ?? [])
    .filter((child) => child.type === "text")
    .map((child) => child.content)
    .join("");
}

describe("a lesson step's heading while it types", () => {
  const STEP = [
    "**1. Subtract 4 from both sides** — Subtraction property of equality",
    "$x + 4 - 4 = 9 - 4$",
    "$x = 5$",
    "",
  ].join("\n");

  // Closed early, "**1. Subtract 4" drew a step badge, lost it when its reason came, and
  // drew it again with the formula (review round 2). Until its line ends it is text.
  it("draws no step badge or numbered list until its line has ended", async () => {
    const heading = STEP.indexOf("\n");
    for (let end = 1; end <= heading; end += 4) {
      const view = await render(<MarkdownContent content={STEP.slice(0, end)} streaming />);
      expect(view.queryByTestId("step-badge")).toBeNull();
      expect(view.queryByTestId("md-ordered-list")).toBeNull();
      await view.unmount();
    }
    const settled = await render(<MarkdownContent content={STEP} />);
    expect(settled.getByTestId("step-badge")).toBeTruthy();
    await settled.unmount();
  }, 30_000);
});
