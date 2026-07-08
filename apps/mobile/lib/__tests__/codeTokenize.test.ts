import { guessLang, looksLikeC, looksLikeJava, resolveHighlightLang, tokenize } from "@/lib/codeTokenize";

describe("resolveHighlightLang", () => {
  it("trusts an explicit, known fence language", () => {
    expect(resolveHighlightLang("python", "x = 1")).toBe("python");
  });

  it("falls back to guessing when the fence language is unknown", () => {
    expect(resolveHighlightLang("made-up-lang", "def add(a, b):\n    return a + b")).toBe(
      "python",
    );
  });
});

describe("guessLang", () => {
  it("guesses python from indentation-style syntax", () => {
    expect(guessLang("def add(a, b):\n    return a + b")).toBe("python");
  });

  it("guesses json from an object literal", () => {
    expect(guessLang('{"foo": "bar"}')).toBe("json");
  });

  it("guesses go from a func declaration", () => {
    expect(guessLang("func main() {\n  fmt.Println(\"hi\")\n}")).toBe("go");
  });
});

describe("looksLikeJava / looksLikeC", () => {
  it("detects a Java main method", () => {
    expect(looksLikeJava("public static void main(String[] args) {}")).toBe(true);
  });

  it("detects a C include", () => {
    expect(looksLikeC("#include <stdio.h>\nint main() { return 0; }")).toBe(true);
  });

  it("rejects unrelated text", () => {
    expect(looksLikeJava("hello world")).toBe(false);
    expect(looksLikeC("hello world")).toBe(false);
  });
});

describe("tokenize", () => {
  it("returns colored tokens for a known language", () => {
    const tokens = tokenize("const x = 1;", "javascript");
    expect(tokens.length).toBeGreaterThan(0);
    expect(tokens.map((t) => t.text).join("")).toBe("const x = 1;");
  });

  it("returns a single plain token for an empty string", () => {
    expect(tokenize("", "javascript")).toEqual([]);
  });

  it("falls back to plain text for a language with no grammar", () => {
    const tokens = tokenize("whatever content", "totally-unknown-lang-xyz");
    expect(tokens.map((t) => t.text).join("")).toBe("whatever content");
  });
});
