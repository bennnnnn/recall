/**
 * No LaTeX source in an exported PDF. Every reply the chat's own leak suite reads
 * (`components/markdown/__tests__/latexLeakCorpus.test.tsx`: the API's behaviour-sweep
 * replies and the shared presentation, physics and chemistry fixtures) is printed as the
 * PDF prints it; with its drawn formulas and its code left out, the text must hold no
 * source (`lib/__tests__/support/latexLeaks.ts`) and none of the placeholders the chat's preprocessing
 * puts in maths. The PDF once printed `R_1 = 2\,\Omega` as a red KaTeX error.
 */
import { markdownToStructuredPrintHtml } from "@/features/chat/model/printDocument";
import { conversationMarkdownBody } from "@/features/chat/model/transcript";
import type { Message } from "@/lib/api";
import { findLatexLeaks } from "@/lib/__tests__/support/latexLeaks";

jest.mock("@/lib/i18n", () => ({
  __esModule: true,
  default: { t: (key: string) => key },
}));

// The features project has no Node types (see lib/__tests__/licenses.test.ts).
declare const __dirname: string;
const { readFileSync, readdirSync } = jest.requireActual<{
  readFileSync(path: string, encoding: "utf8"): string;
  readdirSync(path: string): string[];
}>("node:fs");
const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");

const ROOT = join(__dirname, "..", "..", "..", "..", "..", "..");
const LATEX_LIKE = /\\|\$|[\^_]\{/;
const PLACEHOLDER = /[-]/;

type Entry = { id: string; text: string };

function json<T>(...parts: string[]): T {
  return JSON.parse(readFileSync(join(ROOT, ...parts), "utf8")) as T;
}

function entries(): Entry[] {
  const dir = join("apps", "api", "app", "tests", "behavior", "sweep_corpus");
  const sweep = readdirSync(join(ROOT, dir))
    .filter((file) => file.endsWith(".json"))
    .flatMap((file) =>
      json<{ id: string; reply?: string }[]>(dir, file).map((turn) => ({
        id: `sweep:${file.replace(/\.json$/, "")}:${turn.id}`,
        text: turn.reply ?? "",
      })),
    );
  const presentation = json<{ cases: { id: string; expected: string }[] }>(
    "docs", "fixtures", "presentation_cases.json",
  ).cases.map((c) => ({ id: `presentation:${c.id}`, text: c.expected }));
  const replies = (name: string): Entry[] =>
    Object.entries(json<{ replies: Record<string, { reply: string }> }>("docs", "fixtures", name).replies).map(
      ([id, value]) => ({ id: `${name.replace(/_replies\.json$/, "")}:${id}`, text: value.reply }),
    );
  return [...sweep, ...presentation, ...replies("physics_replies.json"), ...replies("chemistry_replies.json")]
    .filter((entry) => LATEX_LIKE.test(entry.text));
}

/** Leaks the chat's own suite also lists (KNOWN_GAPS there): shared rules, not the PDF's. */
const KNOWN_GAPS: Record<string, string> = {
  "presentation:maths-unclosed": "an unclosed `$` stays as written (a rule shared with the server)",
};

/** What a reader of the PDF sees: its text, without drawn formulas or code. */
function printedText(html: string): string {
  const body = html.slice(html.indexOf("<body>"));
  return body
    .replace(/<svg[\s\S]*?<\/svg>/g, " ")
    .replace(/<pre>[\s\S]*?<\/pre>/g, " ")
    .replace(/<code>[\s\S]*?<\/code>/g, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&");
}

async function leaksOf(entry: Entry): Promise<string[]> {
  const message = { id: "a", role: "assistant", content: entry.text } as Message;
  const html = await markdownToStructuredPrintHtml("T", conversationMarkdownBody([message], "print"));
  const text = printedText(html);
  const found: string[] = findLatexLeaks(text).map((leak) => `${leak.kind} ${leak.text}`);
  if (PLACEHOLDER.test(text) || PLACEHOLDER.test(html)) found.push("placeholder");
  return found;
}

describe("an exported PDF shows no LaTeX source", () => {
  const all = entries();

  it("reads a large corpus", () => {
    expect(all.length).toBeGreaterThan(100);
  });

  it("prints every reply clean", async () => {
    const leaking: string[] = [];
    for (const entry of all) {
      if (entry.id in KNOWN_GAPS) continue;
      const found = await leaksOf(entry);
      if (found.length) leaking.push(`${entry.id}: ${found.join(", ")}`);
    }
    expect(leaking).toEqual([]);
  }, 120_000);

  it("still leaks each known gap: delete it once it prints clean", async () => {
    for (const id of Object.keys(KNOWN_GAPS)) {
      const entry = all.find((candidate) => candidate.id === id);
      expect(entry).toBeDefined();
      expect(await leaksOf(entry!)).not.toEqual([]);
    }
  });

  it("draws a worked answer's subscripts and units", async () => {
    const reply = "**Given**  \n$R_1 = 2\\,\\Omega$  \n$V = 12\\,\\mathrm{V}$\n\n```answer\nverified: true\n2\\,\\mathrm{A}\n```";
    const html = await markdownToStructuredPrintHtml(
      "T",
      conversationMarkdownBody([{ id: "a", role: "assistant", content: reply } as Message], "print"),
    );
    expect(html.match(/<svg/g)?.length).toBe(3);
    expect(html).not.toContain("katex-error");
    expect(printedText(html)).not.toMatch(/\\|Omega|mathrm/);
  });
});
