// Integration coverage for the fence dispatch/splice layer between parsed
// markdown and the Math*/Geometry*/FunctionGraphBlock rich components — zero
// coverage before this file (only each block's own logic was unit tested).
import { render } from "@testing-library/react-native";

import { renderFence, type FenceNode } from "@/components/markdown/markdownFenceRender";

// markdownFenceRender.tsx statically imports CodeBlock/CopyBlock (both pull
// in expo-clipboard + @expo/vector-icons) regardless of which fence branch
// actually runs — this plain @react-native/jest-preset environment (no
// jest-expo) doesn't stub expo-modules-core, so these need simple no-op
// fakes to keep import-time safe. Same pattern as MermaidBlock.test.tsx.
jest.mock("expo-clipboard", () => ({
  setStringAsync: jest.fn(),
}));
jest.mock("expo-web-browser", () => ({
  openBrowserAsync: jest.fn(),
}));
jest.mock("expo-haptics", () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  selectionAsync: jest.fn(),
}));
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  writeAsStringAsync: jest.fn(),
  EncodingType: { UTF8: "utf8" },
}));
jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));
// WebPreviewCodeBlock pulls in expo-file-system (via HtmlPreviewModal ->
// openHtmlPreview) transitively — none of this file's fence bodies are
// html/css/js, so the real component is never actually rendered; a stub
// avoids needing to satisfy that unrelated dependency chain at import time.
jest.mock("@/components/WebPreviewCodeBlock", () => ({
  WebPreviewCodeBlock: "WebPreviewCodeBlock",
}));
// Same reasoning — CircularClockBlock pulls in react-native-reanimated,
// which needs native worklets init unavailable in this test env; none of
// this file's fence bodies are clock content.
jest.mock("@/components/rich/CircularClockBlock", () => ({
  CircularClockBlock: "CircularClockBlock",
}));
// CodeBlock's real syntax-tokenizer loads via a dynamic import() that Jest's
// CJS transform can't resolve without --experimental-vm-modules — a stub
// that just echoes its props is enough to assert dispatch reached it.
jest.mock("@/components/CodeBlock", () => {
  const { Text: RNText } = jest.requireActual("react-native");
  return {
    CodeBlock: ({ code, lang }: { code: string; lang: string }) => (
      <RNText>{`${lang}:${code}`}</RNText>
    ),
  };
});

function node(content: string, info?: string): FenceNode {
  return { key: "k", content, info };
}

describe("renderFence math dispatch", () => {
  it("routes an explicit ```math fence to MathBlock", async () => {
    const { getByText } = await render(<>{renderFence(node("x^2 + 1", "math"))}</>);
    expect(getByText("x² + 1")).toBeOnTheScreen();
  });

  it("routes an untagged fence that looks like LaTeX to MathBlock", async () => {
    const { getByText } = await render(<>{renderFence(node("\\alpha + \\beta"))}</>);
    // No preview WebView in this test env (react-native-webview isn't
    // mocked/linked here) — MathText's plain-Text rendering path is used,
    // same fallback real devices hit outside a dev build.
    expect(getByText("α + β")).toBeOnTheScreen();
  });
});

describe("renderFence math key stability", () => {
  it("BUG FIX regression: identical latex gets the same React key across re-parses, not the volatile node.key react-native-markdown-display regenerates every parse", () => {
    // Simulates two independent parses of the same still-growing streaming
    // reply: react-native-markdown-display assigns a fresh node.key each
    // time, but MathBlock's WebView-backed renderer must not remount (a
    // full WebView reload, visible as a flicker) just because the wrapping
    // node.key changed while the underlying latex stayed identical.
    const first = renderFence(node("x^2 + 1", "math"));
    const second = renderFence({
      key: "a-totally-different-node-key-from-the-next-parse",
      content: "x^2 + 1",
      info: "math",
    });

    expect(first?.key).toBeTruthy();
    expect(first?.key).toBe(second?.key);
  });

  it("gives different latex content different keys", () => {
    const a = renderFence(node("x^2 + 1", "math"));
    const b = renderFence(node("y^2 + 1", "math"));

    expect(a?.key).not.toBe(b?.key);
  });

  it("BUG FIX regression: two fences with identical latex get distinct keys via tokenIndex (no duplicate React key warning)", () => {
    // Reported live: `\pm 2` appeared twice in one reply and React warned
    // "Encountered two children with the same key, `math:\pm 2`". The
    // content-derived key must be disambiguated by the fence's stable
    // tokenIndex so sibling MathBlocks don't collide, while remaining
    // stable across re-parses for the *same* fence.
    const first = renderFence({
      key: "k1",
      content: "\\pm 2",
      info: "math",
      tokenIndex: 5,
    });
    const second = renderFence({
      key: "k2",
      content: "\\pm 2",
      info: "math",
      tokenIndex: 9,
    });

    expect(first?.key).toBeTruthy();
    expect(first?.key).not.toBe(second?.key);
    // The same fence re-parsed (same content + same tokenIndex, fresh
    // volatile node.key) must keep its key — no MathBlock remount/flicker.
    const firstReparsed = renderFence({
      key: "a-fresh-volatile-node-key",
      content: "\\pm 2",
      info: "math",
      tokenIndex: 5,
    });
    expect(firstReparsed?.key).toBe(first?.key);
  });
});

describe("renderFence geometry/graph dispatch", () => {
  it("routes an explicit ```geometry fence to GeometryBlock", async () => {
    const content = JSON.stringify({ type: "square", side: 5, unit: "cm" });
    const { toJSON } = await render(<>{renderFence(node(content, "geometry"))}</>);
    expect(JSON.stringify(toJSON())).toContain("RNSVGSvgView");
  });

  it("routes an explicit ```graph fence to FunctionGraphBlock", async () => {
    const content = JSON.stringify({
      type: "function",
      expr: "x**2",
      points: [
        [0, 0],
        [1, 1],
      ],
    });
    const { getByText } = await render(<>{renderFence(node(content, "graph"))}</>);
    expect(getByText("y = x**2")).toBeOnTheScreen();
  });

  it("sniffs an untagged ```json geometry blob and routes it to GeometryBlock", async () => {
    // The model routinely emits ```json (or an untagged fence) instead of
    // the ```geometry it's told to use — RichFence's content-sniffing
    // fallback (detectJsonRichFenceKind) must still route it correctly.
    const content = JSON.stringify({ type: "rectangle", width: 6, height: 4, unit: "cm" });
    const { toJSON } = await render(<>{renderFence(node(content, "json"))}</>);
    expect(JSON.stringify(toJSON())).toContain("RNSVGSvgView");
  });

  it("sniffs an untagged fence graph blob and routes it to FunctionGraphBlock", async () => {
    const content = JSON.stringify({
      type: "function",
      expr: "sin(x)",
      points: [
        [0, 0],
        [1, 0.84],
      ],
    });
    const { getByText } = await render(<>{renderFence(node(content))}</>);
    expect(getByText("y = sin(x)")).toBeOnTheScreen();
  });
});

describe("renderFence edge cases", () => {
  it("renders nothing for a whitespace-only fence body", () => {
    expect(renderFence(node("   \n  "))).toBeNull();
  });

  it("falls back to CodeBlock for a plain code fence with an explicit language", async () => {
    const { getByText } = await render(<>{renderFence(node("const x = 1;", "javascript"))}</>);
    expect(getByText("javascript:const x = 1;")).toBeOnTheScreen();
  });

  it("routes a short numeric final (including mis-tagged ```copy) to AnswerBlock, not Copy", async () => {
    const { getByLabelText, queryByText } = await render(
      <>{renderFence(node("120", "copy"))}</>,
    );
    expect(getByLabelText("Answer: 120")).toBeOnTheScreen();
    expect(queryByText("Copy")).toBeNull();
  });

  it("routes an explicit ```answer fence to AnswerBlock", async () => {
    const { getByLabelText } = await render(<>{renderFence(node("120", "answer"))}</>);
    expect(getByLabelText("Answer: 120")).toBeOnTheScreen();
  });

  it("routes a factorial definition (mis-tagged ```copy) to MathBlock without Copy", async () => {
    const { getByText, queryByText } = await render(
      <>{renderFence(node("0! = 1", "copy"))}</>,
    );
    expect(getByText(/0!/)).toBeOnTheScreen();
    expect(queryByText("Copy")).toBeNull();
  });

  it("BUG FIX regression: routes a bare simplified expression with no lang tag or ```copy to AnswerBlock, not Copy", async () => {
    // Reported live: "2c^2" (a simplified final result, no "=") fell through
    // every existing looksLikeMathAnswer branch and landed on the generic
    // CodeBlock fallback, which shows a "Copy" button.
    const { getByLabelText, queryByText } = await render(
      <>{renderFence(node("2c^2", "copy"))}</>,
    );
    expect(getByLabelText("Answer: 2c^2")).toBeOnTheScreen();
    expect(queryByText("Copy")).toBeNull();
  });

  it("BUG FIX regression: an explicit ```math fence is never reinterpreted as an Answer even if its content looks answer-like", async () => {
    // looksLikeMathAnswer was broadened to catch bare expressions like
    // "2c^2" — without a lang guard at the call site, that same heuristic
    // started misrouting explicitly ```math-tagged content (e.g. "x^2 + 1",
    // a legitimate intermediate step) to AnswerBlock instead of MathBlock.
    const { getByText } = await render(<>{renderFence(node("x^2 + 1", "math"))}</>);
    expect(getByText("x² + 1")).toBeOnTheScreen();
  });
});
