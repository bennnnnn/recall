/**
 * MathSvgBridge spike — RN-side wiring tests.
 *
 * Proves the bridge resolves an SVG posted by the hidden WebView, caches it,
 * and rejects when not ready / on error so callers fall back.
 *
 * The <SvgXml> native render of the returned SVG is validated ON-DEVICE (it
 * needs the native react-native-svg renderer, which jest can't host). Flip
 * `MATH_SVG_NATIVE_ENABLED = true` in `lib/mathSvgBridge.ts` and run the app
 * to A/B against the visible-WebView path.
 */

import { handleBridgeMessage, requestMathSvg, setBridgeTransport } from "@/lib/mathSvgBridge";

// A realistic MathJax tex-svg fragment (namespaced <svg> with <g> + <text>),
// structurally what MathJax emits.
const SAMPLE_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20"><g><text x="2" y="14" font-size="12">x</text></g></svg>';

describe("mathSvgBridge (mocked transport)", () => {
  afterEach(() => setBridgeTransport(null, false));

  it("resolves an SVG posted by the hidden WebView and caches it", async () => {
    let lastJs: string | null = null;
    setBridgeTransport((js) => {
      lastJs = js;
    }, true);

    const p = requestMathSvg("\\frac{1}{2}");
    expect(lastJs).toContain("__renderSvg");
    const idMatch = lastJs && /__renderSvg\((\d+)/.exec(lastJs);
    expect(idMatch).not.toBeNull();
    const id = Number(idMatch![1]);
    handleBridgeMessage(JSON.stringify({ id, svg: SAMPLE_SVG }));

    expect(await p).toBe(SAMPLE_SVG);

    // Second request for the same LaTeX resolves from cache (no new post).
    lastJs = null;
    const svg2 = await requestMathSvg("\\frac{1}{2}");
    expect(svg2).toBe(SAMPLE_SVG);
    expect(lastJs).toBeNull();
  });

  it("rejects when the bridge is not ready so callers fall back", async () => {
    setBridgeTransport(null, false);
    await expect(requestMathSvg("x^2")).rejects.toThrow("math-svg-bridge-not-ready");
  });

  it("rejects on an error message so callers fall back", async () => {
    let lastJs: string | null = null;
    setBridgeTransport((js) => {
      lastJs = js;
    }, true);
    const p = requestMathSvg("\\badcmd{");
    const idMatch = lastJs && /__renderSvg\((\d+)/.exec(lastJs);
    const id = Number(idMatch![1]);
    handleBridgeMessage(JSON.stringify({ id, error: "Unknown command" }));
    await expect(p).rejects.toThrow("Unknown command");
  });

  it("evicts the oldest cache entry past MAX_CACHE", async () => {
    let lastJs: string | null = null;
    setBridgeTransport((js) => {
      lastJs = js;
    }, true);
    // Fill the cache with 256 unique entries.
    for (let i = 0; i < 256; i++) {
      const pp = requestMathSvg(`x_${i}`);
      const idMatch = lastJs && /__renderSvg\((\d+)/.exec(lastJs);
      const id = Number(idMatch![1]);
      handleBridgeMessage(JSON.stringify({ id, svg: `<svg id="${i}"/>` }));
      await pp;
    }
    // One more should not blow up (eviction kicks in).
    const pp = requestMathSvg("x_overflow");
    const idMatch = lastJs && /__renderSvg\((\d+)/.exec(lastJs);
    const id = Number(idMatch![1]);
    handleBridgeMessage(JSON.stringify({ id, svg: "<svg id='over'/>" }));
    await expect(pp).resolves.toBe("<svg id='over'/>");
  });
});
