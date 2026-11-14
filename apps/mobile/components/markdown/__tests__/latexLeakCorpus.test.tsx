/**
 * No LaTeX source on screen. Every reply below is rendered through
 * MarkdownContent and the text a reader sees, and the labels a screen reader
 * hears, are scanned for source (`lib/__tests__/support/latexLeaks.ts`). Display maths is
 * drawn here by the native fallback, the stricter of its two renderers; each
 * formula also goes through MathJax, whose SVG must never paint a backslash.
 * A reply may also not use a command the native renderer has no entry for.
 *
 * Corpora: the API's behaviour-sweep replies, the shared presentation cases,
 * the physics and chemistry reply fixtures, and the variants at the bottom.
 * An entry in KNOWN_GAPS must still fail: delete it once it renders clean.
 */
import { cleanup, render } from "@testing-library/react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { findLatexLeaks } from "@/lib/__tests__/support/latexLeaks";
import { subscribeUnknownLatexCommands } from "@/lib/math/latexNames";
import { latexToSvgMath } from "@/lib/math/svgMath";

jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  writeAsStringAsync: jest.fn(),
  EncodingType: { UTF8: "utf8" },
}));
jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: () => null }));
// Code is source a reader asked for, not prose: leave it out of the scan.
jest.mock("@/components/CodeBlock", () => ({ CodeBlock: () => null }));
jest.mock("@/components/markdown/InlineCode", () => ({ InlineCode: () => null }));
jest.mock("@/components/WebPreviewCodeBlock", () => ({ WebPreviewCodeBlock: () => null }));
jest.mock("@/components/rich/CircularClockBlock", () => ({ CircularClockBlock: () => null }));
// The suite's Jest env cannot evaluate React.lazy imports: draw the real blocks eagerly.
jest.mock("@/components/rich/LazyHeavyRich", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports -- jest mock factory
  const React = require("react");
  // eslint-disable-next-line @typescript-eslint/no-require-imports -- jest mock factory
  const { GeometryBlock } = require("@/components/rich/GeometryBlock");
  // eslint-disable-next-line @typescript-eslint/no-require-imports -- jest mock factory
  const { FunctionGraphBlock } = require("@/components/rich/FunctionGraphBlock");
  return {
    ...jest.requireActual("@/components/rich/LazyHeavyRich"),
    LazyGeometryBlock: ({ content }: { content: string }) => React.createElement(GeometryBlock, { content }),
    LazyFunctionGraphBlock: ({ content }: { content: string }) =>
      React.createElement(FunctionGraphBlock, { content }),
    LazyMolecule3DBlock: () => null,
    LazyMoleculeCard: () => null,
    LazyCircularClockBlock: () => null,
    LazyWebPreviewCodeBlock: () => null,
  };
});
const mockDisplayMaths: string[] = [];
jest.mock("@/components/rich/MathSvgView", () => {
  const React = jest.requireActual("react");
  const { MathText } = jest.requireActual("@/components/rich/MathText");
  return {
    MathSvgView: ({ latex }: { latex: string }) => {
      mockDisplayMaths.push(latex);
      return React.createElement(MathText, { latex });
    },
  };
});

// The components project has no Node types (see lib/__tests__/licenses.test.ts).
declare const __dirname: string;
const { readFileSync, readdirSync } = jest.requireActual<{
  readFileSync(path: string, encoding: "utf8"): string;
  readdirSync(path: string): string[];
}>("node:fs");
const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");

const ROOT = join(__dirname, "..", "..", "..", "..", "..");
const LATEX_LIKE = /\\|\$|[\^_]\{/;

type Entry = { id: string; text: string };

function json<T>(...parts: string[]): T {
  return JSON.parse(readFileSync(join(ROOT, ...parts), "utf8")) as T;
}

function sweepReplies(): Entry[] {
  const dir = join("apps", "api", "app", "tests", "behavior", "sweep_corpus");
  return readdirSync(join(ROOT, dir))
    .filter((file) => file.endsWith(".json"))
    .flatMap((file) =>
      json<{ id: string; reply?: string }[]>(dir, file).map((turn) => ({
        id: `sweep:${file.replace(/\.json$/, "")}:${turn.id}`,
        text: turn.reply ?? "",
      })),
    );
}

function fixtureReplies(): Entry[] {
  const presentation = json<{ cases: { id: string; input: string; expected: string }[] }>(
    "docs", "fixtures", "presentation_cases.json",
  ).cases.flatMap((c) => [
    { id: `presentation:${c.id}:input`, text: c.input },
    { id: `presentation:${c.id}:expected`, text: c.expected },
  ]);
  const replies = (name: string): Entry[] =>
    Object.entries(json<{ replies: Record<string, { reply: string }> }>("docs", "fixtures", name).replies).map(
      ([id, value]) => ({ id: `${name.replace(/_replies\.json$/, "")}:${id}`, text: value.reply }),
    );
  return [...presentation, ...replies("physics_replies.json"), ...replies("chemistry_replies.json")];
}

/** What models write that the corpora above hold too little of. */
const VARIANTS: Record<string, string> = {
  "symbols": "The expected value is $\\mathbb{E}[X] = 3$, the angle $\\varphi = 30^\\circ$, the length $\\ell$.",
  "bars": "So $\\vert x \\vert = 3$ and $\\lVert v \\rVert = 1$.",
  "nested box": "So the answer is $\\boxed{x=\\frac{1}{2}}$.",
  "labelled arrow": "Heating gives $A \\xrightarrow{\\Delta} B$ and $\\ce{2H2 + O2 -> 2H2O}$.",
  "units": "The weight is $F = \\SI{9.8}{\\newton}$ and $g = \\SI{9.8}{\\meter\\per\\second\\squared}$.",
  "bold vectors": "$$\\bm{F} = m\\bm{a}$$",
  "reals": "$$x \\in \\R, \\; y \\in \\mathbb{N}$$",
  "operators": "The sign is $\\sgn(x)$ and $\\lcm(4, 6) = 12$.",
  "physics package": "Then $\\abs{x} = 2$ and $\\dv{f}{x} = 3x^2$.",
  "colour": "Highlight $\\textcolor{red}{x + 1}$ and ${\\color{blue} y}$.",
  "spacing": "So $x\\hspace{1em}y$, $a\\,b\\;c\\:d\\!e$ and $\\phantom{0}1$.",
  "paren delimiters": "Half is \\( \\frac{1}{2} \\) and \\[ \\int_0^1 x\\,dx = \\tfrac{1}{2} \\]",
  "environments": "$$\\begin{cases} x + y = 3 \\\\ x - y = 1 \\end{cases}$$\n\n$$\\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}$$",
  "aligned": "$$\\begin{aligned} a &= b + c \\\\ &= d \\end{aligned}$$",
  "math fence": "```math\n\\frac{a}{b} = \\sqrt{\\frac{c}{d}}\n```",
  "latex fence": "```latex\nE = mc^2\n```",
  "list and heading": "### Step $1$: find $\\theta$\n\n1. Use $\\sin\\theta = \\frac{o}{h}$\n2. So **$\\theta = 30^\\circ$**",
  "quote": "> Note: $\\Delta x = v\\,\\Delta t$",
  "big operators": "$\\sum\\limits_{i=1}^{n} i = \\frac{n(n+1)}{2}$ and $\\prod_{k=1}^{3} k = 6$",
  "negation": "$a \\not\\in B$ and $x \\not= y$",
  "binomial": "$\\binom{\\frac{n}{2}}{k}$ and $\\dbinom{5}{2} = 10$",
  "line break inline": "$x = 1 \\\\ y = 2$",
  // SymPy braces every function's argument; a follow-up copied a degree in a text group.
  "sympy arguments": "So $y = \\ln{\\left(x^{2} + 1 \\right)}$ and $\\int x \\sin{\\left(x \\right)}\\,dx$.",
  "text group command": "What if $\\theta$ was $45^\\text{\\textdegree}$ instead?",
  "formula of words": "They always satisfy one rule:\n\n$Assets = Liabilities + Equity$\n\nAlways.",
  "unit circle":
    '```arithmetic\n{"type":"unit_circle","degrees":30,"radians":"\\\\frac{\\\\pi}{6}","cosine":"\\\\frac{\\\\sqrt{3}}{2}","sine":"\\\\frac{1}{2}","tangent":"\\\\frac{\\\\sqrt{3}}{3}","plot_x":0.866025,"plot_y":0.5,"answer":"\\\\frac{1}{2}","speech":"30 degrees is the point with cosine \\\\frac{\\\\sqrt{3}}{2} and sine \\\\frac{1}{2}."}\n```',
  "price beside maths": "It costs $5, and $4! = 4 \\times 3 \\times 2 \\times 1 = 24$.",
  // The owner's "How" reply (2026-11-11): a factorial alone read as a price, drawn "$4!$".
  "factorial alone": "**Given**\n\n$4!$\n\nSo $4! + 3! = 30$ and $n!$ grows fast.",
  // Money worked with TeX operators and no maths delimiters of its own.
  "price times": "- Hotel: $80 \\times 7 = $560",
  "price cdot": "Total: $80 \\cdot 7 = $560 for the week.",
  "price line": "$12 \\times 3 = $36",
  "price fraction": "$5 + \\frac{1}{2} = $5.50",
  "price times price": "$2 \\times $3 = $6",
  "price bold label": "**Total:** $80 \\times 7 = $560",
  "escaped prices in maths": "$\\$80 \\times 7 = \\$560$",
  // Rich cards draw their own text: each must draw its maths too.
  "steps":
    "```steps\n1. Add 9: $x^2+6x+9 = 16$\n2. Take the root: **$x + 3 = \\pm 4$**\n3. So $x = \\frac{1}{2}$ or `x = -7`\n```",
  "quiz options":
    '```quiz\n{"question": "What is $\\\\frac{1}{2} + \\\\frac{1}{4}$?", "options": ["$\\\\frac{3}{4}$", "$\\\\frac{2}{6}$"], "answer": 0, "explanation": "Add the quarters."}\n```',
  "quiz plain body": "```quiz\nSolve $x^2 = 9$ for $x$.\n```",
  "callout": "```tip\nComplete the square: $(x+3)^2 = 16$.\n```",
  // The phone test of 2026-11-11 (DeepSeek, laid out by the server): maths left bare in a
  // formula's heading and a move's note, and the heading the server now writes.
  "worked heading with bare maths": "**Given**  \n$I = \\int_0^1 \\frac{\\ln(1+x)}{1+x^2}\\,dx$  \nwhere $I$ = definite integral\n\n**Required**  \n$I$ (value of the definite integral)\n\n**Solution**\n\n**Substitution x = \\tan t formula**  \n$I = \\int_0^{\\pi/4} \\ln(1+\\tan t)\\,dt$  \n$1+\\tan t = \\frac{\\sqrt{2}\\cos\\left(t-\\frac{\\pi}{4}\\right)}{\\cos t}$ — trigonometric identity  \n$\\int_0^{\\pi/4} \\ln\\cos\\left(t-\\frac{\\pi}{4}\\right)\\,dt = \\int_0^{\\pi/4}\\ln\\cos t\\,dt$ — evenness of \\ln\\cos t\n\n**Substitution**  \n$I = \\frac{\\pi}{8}\\ln 2 + \\int_0^{\\pi/4}\\ln\\cos\\left(t-\\frac{\\pi}{4}\\right)\\,dt - \\int_0^{\\pi/4}\\ln\\cos t\\,dt$  \n$I = \\frac{\\pi}{8}\\ln 2$\n\n**Answer**",
  "worked notes with bare maths": "**Given**  \n$y(0) = 1$  \n$x = \\pi/3\\,\\mathrm{rad}$  \nwhere $y(0)$ = initial condition, $x$ = point where y is evaluated\n\n**Required**  \n$y(\\pi/3)$ (value of the solution at x = \\pi/3)\n\n**Solution**\n\n**Integrating factor method**  \n$\\frac{dy}{dx} + y\\tan x = \\cos^{3}x$  \n$\\mu = e^{\\int \\tan x\\,dx}$ — Integrating factor  \n$\\mu = \\sec x$  \n$y\\sec x = \\int \\sec x\\cos^{3}x\\,dx$ — multiply through by \\mu = \\sec x  \n$y\\sec x = \\int \\cos^{2}x\\,dx$ — simplify the right-hand side  \n$y\\sec x = \\frac{x}{2} + \\frac{\\sin 2x}{4} + C$ — integrate  \nSolve for $y$  \n$y = \\cos x\\left(\\frac{x}{2} + \\frac{\\sin 2x}{4} + C\\right)$  \n$1 = \\cos 0\\left(0 + 0 + C\\right)$ — apply y(0) = 1  \n$C = 1$ — solve for C\n\n**Substitution**  \n$y = \\cos\\frac{\\pi}{3}\\left(\\frac{\\pi/3}{2} + \\frac{\\sin(2\\pi/3)}{4} + 1\\right)$  \n$y = \\frac{1}{2}\\left(\\frac{\\pi}{6} + \\frac{\\sqrt{3}}{8} + 1\\right)$  \n$y = \\frac{\\pi}{12} + \\frac{\\sqrt{3}}{16} + \\frac{1}{2}$  \n$y = 0.870$\n\n**Answer**",
  "worked heading ending on maths":
    "**Solution**\n\n**Substitution $x = \\tan t$**  \n$I = \\int_0^{\\pi/4} \\ln(1+\\tan t)\\,dt$  \n" +
    "$1+\\tan t = \\frac{\\sqrt{2}\\cos t}{\\cos t}$ — evenness of $\\ln\\cos t$",
  // A note's maths the server marks as one run, never "$…$$…$" (review, 2026-11-11).
  "worked note with maths glued to a fraction":
    "**Solution**\n\n**Rolling without slipping formula**  \n$a = \\frac{g\\sin\\theta}{1 + \\frac{I}{MR^2}}$ — using $I = \\frac{1}{2}MR^2$ for a disc  \n" +
    "$E = mgh$ — energy goes to $KE = \\frac{1}{2}mv^2$, the price is \\$5",
  "worked formula with no name":
    "**Given**  \n$k = 400\\,\\mathrm{N/m}$\n\n**Solution**\n\n$m g h = \\frac{1}{2} k x^{2}$  \nSolve for $x$  \n$x = \\sqrt{\\frac{2 m g h}{k}}$",
  // A word symbol's subscript a model escaped for text mode, braced by the layout before
  // 2026-11-12 (drawn "white_{pigment}"), and as the layout writes it now.
  "worked word symbol escaped":
    "**Substitution**  \n$\\text{gallons per part} = \\frac{\\text{total\\_{paint}}}{\\text{ratio\\_{total}}}$  \n" +
    "$\\text{white\\_{pigment}} = 3 \\times 4$",
  "worked word symbol":
    "**Required**  \n(a) $white_{pigment}$ (gallons of white pigment)\n\n**Substitution**  \n" +
    "$white_{pigment} = 3 \\times 4$  \n$\\text{cost}_{\\text{per}}\\text{ item} = 12\\,\\mathrm{gal}$",
  // A ratio's dollars padded inside (the textbook run, 2026-11-13): "$9:" read as a price
  // left "3: 4: 5$" on screen and set "is the" in maths italics.
  "padded ratios": "- **Check** — $9: 12: 15 $ is the $ 3: 4: 5$ ratio, so the result fits.",
  "ratios": "The sides are in the ratio $9: 12: 15$, which is $3: 4: 5$ scaled by $3$.",
  // A price before a colon and a number stays a price beside the maths after it (review of
  // the ratio fix, 2026-11-13: the fraction was lost, or drawn as "$frac{1200}{3}").
  "price colon then a fraction":
    "Rent is $1,200: 3 roommates each pay $\\frac{1200}{3} = 400$. The bill is $90: 3 of us split it as $\\frac{90}{3}$.",
  "price colon then an equation": "Total $60: 3 of us, so $x = 20$. Budget $50: 2 shirts at $s$ each.",
  // Known gaps (see KNOWN_GAPS): each is a leak this suite still finds.
  "table abs": "| Expression | Value |\n|---|---|\n| $|x-3|$ | 5 |",
  "bare script": "The area is 25 m^{2}.",
  "bare tex in prose": "The speed is v = 5\\,\\text{m/s} and KE = \\frac{1}{2}mv^{2} here.",
  "unclosed dollar": "So $v = 5 and we are done.",
};

const ENTRIES: Entry[] = [
  ...sweepReplies(),
  ...fixtureReplies(),
  ...Object.entries(VARIANTS).map(([id, text]) => ({ id: `variant:${id}`, text })),
].filter((entry) => LATEX_LIKE.test(entry.text));

/** Entries that leak today, with why. Each must still leak: delete it once fixed. */
const KNOWN_GAPS: Record<string, string> = {
  "presentation:maths-unclosed:input": "an unclosed `$` stays as written (a rule shared with the server)",
  "presentation:maths-unclosed:expected": "an unclosed `$` stays as written (a rule shared with the server)",
  "variant:unclosed dollar": "an unclosed `$` stays as written",
  "variant:bare script": "a TeX script outside `$` (`m^{2}`) is not wrapped as maths",
  "variant:bare tex in prose": "a TeX script outside `$` (`mv^{2}`) is not wrapped as maths",
  "variant:table abs": "a `|` inside maths in a table cell splits the cell",
};

function textOf(node: any, seen: { visible: string[]; labels: string[] }): void {
  if (node == null || typeof node === "boolean") return;
  if (typeof node === "string" || typeof node === "number") {
    seen.visible.push(String(node));
    return;
  }
  if (Array.isArray(node)) {
    node.forEach((child) => textOf(child, seen));
    return;
  }
  const label = node.props?.accessibilityLabel;
  if (typeof label === "string") seen.labels.push(label);
  (node.children ?? []).forEach((child: any) => textOf(child, seen));
}

/** Each leak in `text`, with the words around it. */
function leaksIn(text: string): string[] {
  return findLatexLeaks(text).map(
    (leak) => `${leak.kind} ${JSON.stringify(leak.text)} in ${JSON.stringify(text.slice(Math.max(0, leak.index - 30), leak.index + 40))}`,
  );
}

/** What a reader of `text` would see as source, and the command names nothing could draw.
 * The visible pieces are read as one text: a table cell can split `$` from its maths. */
async function scan(text: string): Promise<{ seen: string; leaks: string[]; unknown: string[] }> {
  const unknown = new Set<string>();
  const unsubscribe = subscribeUnknownLatexCommands((name) => unknown.add(name));
  mockDisplayMaths.length = 0;
  const screen = await render(<MarkdownContent content={text} />);
  const seen = { visible: [] as string[], labels: [] as string[] };
  textOf(screen.toJSON(), seen);
  screen.unmount();
  unsubscribe();
  const visible = seen.visible.join("");
  const leaks = [...leaksIn(visible), ...seen.labels.flatMap(leaksIn)];
  for (const latex of [...mockDisplayMaths]) {
    const svg = (await latexToSvgMath(latex, true))?.svg ?? "";
    if (svg.includes('data-c="5C"')) leaks.push(`MathJax paints a backslash for ${JSON.stringify(latex)}`);
  }
  return { seen: visible, leaks, unknown: [...unknown] };
}

async function problems(text: string): Promise<string[]> {
  const { leaks, unknown } = await scan(text);
  return [...leaks, ...unknown.map((name) => `unknown command \\${name}`)];
}

/** Replies still streaming in: the text at every 41st character, as the stream draws it.
 * A half-written command is no problem here; source on screen is. */
async function streamingProblems(text: string): Promise<string[]> {
  const found: string[] = [];
  for (let cut = 8; cut < text.length; cut += 41) {
    const screen = await render(<MarkdownContent content={text.slice(0, cut)} streaming />);
    const seen = { visible: [] as string[], labels: [] as string[] };
    textOf(screen.toJSON(), seen);
    await cleanup();
    const leaks = [...leaksIn(seen.visible.join("")), ...seen.labels.flatMap(leaksIn)];
    found.push(...leaks.map((leak) => `at ${cut}: ${leak}`));
  }
  return found;
}

/** Streaming entries that show source today, with why. Each must still: delete it once fixed. */
const STREAMING_KNOWN_GAPS: Record<string, string> = {
  "presentation:escaped-currency-in-formula:input":
    "the stream tail's presentation wraps an unfinished formula holding `\\$` as display maths",
  "presentation:escaped-currency-in-formula:expected":
    "the stream tail's presentation wraps an unfinished formula holding `\\$` as display maths",
  "variant:escaped prices in maths":
    "the stream tail's presentation wraps an unfinished formula holding `\\$` as display maths",
};

const clean = ENTRIES.filter((entry) => !(entry.id in KNOWN_GAPS));
const gaps = ENTRIES.filter((entry) => entry.id in KNOWN_GAPS);
const streamingClean = ENTRIES.filter((entry) => !(entry.id in STREAMING_KNOWN_GAPS));
const streamingGaps = ENTRIES.filter((entry) => entry.id in STREAMING_KNOWN_GAPS);

describe("LaTeX never reaches the screen as source", () => {
  it("covers the corpora", () => {
    expect(ENTRIES.length).toBeGreaterThan(400);
    expect(Object.keys(KNOWN_GAPS).filter((id) => !ENTRIES.some((entry) => entry.id === id))).toEqual([]);
  });

  it("draws an unknown command's argument, never its name, and reports the name", async () => {
    const { seen, leaks, unknown } = await scan("The value $\\nosuchcommand{x} = 2$ stays readable.");
    expect(leaks).toEqual([]);
    expect(seen).not.toContain("nosuchcommand");
    expect(unknown).toEqual(["nosuchcommand"]);
  });

  it("finds a closing dollar a reader would see, never a price's", () => {
    expect(leaksIn("the 3: 4: 5$ ratio")).not.toEqual([]);
    expect(leaksIn("so x$, then (a + b)$.")).toHaveLength(2);
    expect(leaksIn("It costs $5, US$5 or $ 19.20; a ($$) place.")).toEqual([]);
  });

  it.each(clean.map((entry) => [entry.id, entry.text]))("%s", async (_id, text) => {
    expect(await problems(text)).toEqual([]);
  });

  if (gaps.length) {
    it.each(gaps.map((entry) => [entry.id, entry.text]))("%s still leaks (known gap)", async (_id, text) => {
      expect(await problems(text)).not.toEqual([]);
    });
  }
});

// A long reply renders at many cut points; under a full parallel run that outlasts Jest's 5 s.
const STREAMING_TIMEOUT_MS = 60_000;

describe("LaTeX never reaches the screen as source while a reply streams in", () => {
  it.each(streamingClean.map((entry) => [entry.id, entry.text]))(
    "%s",
    async (_id, text) => {
      expect(await streamingProblems(text)).toEqual([]);
    },
    STREAMING_TIMEOUT_MS,
  );

  if (streamingGaps.length) {
    it.each(streamingGaps.map((entry) => [entry.id, entry.text]))(
      "%s still leaks while streaming (known gap)",
      async (_id, text) => {
        expect(await streamingProblems(text)).not.toEqual([]);
      },
      STREAMING_TIMEOUT_MS,
    );
  }
});
