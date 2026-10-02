import {
  buildSmilesDrawerHtml,
  readSmilesDrawerError,
  SMILES_DRAWER_ERROR_KIND,
} from "@/lib/chemistry/smilesDrawerHtml";

const THEME = { bg: "#ffffff", isDark: false };

/** The template literal the page assigns the SMILES to, evaluated the way the page would. */
function smilesAsPageReadsIt(html: string): string {
  const match = /var smiles = `([\s\S]*?)`;\n\s*function reportError/.exec(html);
  if (!match) throw new Error("the page has no smiles literal");
  return new Function(`return \`${match[1]}\`;`)() as string;
}

describe("buildSmilesDrawerHtml", () => {
  it("hands an ordinary SMILES to the page unchanged", () => {
    expect(smilesAsPageReadsIt(buildSmilesDrawerHtml("CC(=O)Oc1ccccc1C(=O)O", THEME))).toBe(
      "CC(=O)Oc1ccccc1C(=O)O",
    );
  });

  it.each([
    ["a backtick", "C`C"],
    ["a template placeholder", "C${alert(1)}C"],
    ["a backslash", "C\\C"],
    ["a closing script tag", "C</script><script>alert(1)</script>"],
    ["a comment opener before a script tag", "C<!--<script>"],
    ["a line break", "C\nC"],
  ])("cannot be broken out of by %s", (_name, hostile) => {
    const html = buildSmilesDrawerHtml(hostile, THEME);
    expect(smilesAsPageReadsIt(html)).toBe(hostile);
    // The script ends once, at its own closing tag, and no comment opener reaches the page
    // (`<!--` before `<script` would stop that closing tag from ending it).
    expect(html.match(/<\/script>/gi)).toHaveLength(1);
    expect(html).not.toContain("<!--");
  });

  it("trims the SMILES it draws", () => {
    expect(smilesAsPageReadsIt(buildSmilesDrawerHtml("  CCO \n", THEME))).toBe("CCO");
  });

  it("carries the content security policy and no network access", () => {
    const html = buildSmilesDrawerHtml("CCO", THEME);
    expect(html).toContain("Content-Security-Policy");
    expect(html).toContain("connect-src 'none'");
  });

  it("follows the theme", () => {
    expect(buildSmilesDrawerHtml("CCO", { bg: "#101010", isDark: true })).toContain(
      "background:#101010",
    );
    expect(buildSmilesDrawerHtml("CCO", { bg: "#101010", isDark: true })).toContain("'dark'");
    expect(buildSmilesDrawerHtml("CCO", THEME)).toContain("'light'");
  });

  it("reports failure by code, leaving the words to the app", () => {
    const html = buildSmilesDrawerHtml("CCO", THEME);
    expect(html).toContain(`kind: '${SMILES_DRAWER_ERROR_KIND}'`);
    expect(html).toContain("reportError('render')");
    expect(html).toContain("reportError('unavailable')");
    expect(html).toContain("try {\n  var drawer = new SmilesDrawer.SvgDrawer");
    expect(html).not.toContain("Could not render");
  });
});

describe("readSmilesDrawerError", () => {
  const message = (code: unknown) => JSON.stringify({ kind: SMILES_DRAWER_ERROR_KIND, code });

  it("reads the page's error codes", () => {
    expect(readSmilesDrawerError(message("render"))).toBe("render");
    expect(readSmilesDrawerError(message("unavailable"))).toBe("unavailable");
  });

  it("treats a code it does not know as a failed drawing", () => {
    expect(readSmilesDrawerError(message("something-new"))).toBe("render");
  });

  it.each([
    ["nothing", undefined],
    ["an empty string", ""],
    ["text that is not JSON", "hello"],
    ["JSON that is not an object", "42"],
    ["null", "null"],
    ["another kind of message", JSON.stringify({ kind: "loaded" })],
  ])("ignores %s", (_name, data) => {
    expect(readSmilesDrawerError(data)).toBeNull();
  });
});
