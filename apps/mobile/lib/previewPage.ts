/**
 * A preview WebView page (a Mermaid diagram, a chart, a SMILES drawing) is
 * built once from its vendored libraries and loaded from a file
 * (lib/previewPageFile.ts). The page holds no block's data: each WebView hands
 * its own (the diagram source, the chart spec, the SMILES) to the page script.
 */

/** A page built from named libraries; `build` gets each library's source. */
export type PreviewPage<L extends string = string> = {
  /** Names the page's file, so one name per page. */
  name: string;
  libraries: readonly L[];
  build: (sources: Readonly<Record<L, string>>) => string;
};

/** One block's data, as the page script reads it. */
export type PreviewPageConfig = Record<string, unknown>;

/** Where the page finds its block's data, and the function that starts it. */
const CONFIG_GLOBAL = "RECALL_PREVIEW";
const START_GLOBAL = "RECALL_PREVIEW_START";

/**
 * The script that hands a block's data to its page. The WebView runs it before
 * the page loads and again once it has (`injectedJavaScriptBeforeContentLoaded`
 * and `injectedJavaScript`): Android may run the first one too late, or on the
 * document being replaced. The data is a JSON literal, so it cannot end the script.
 */
export function previewPageConfigScript(config: PreviewPageConfig): string {
  const json = JSON.stringify(config).replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029");
  return (
    `window.${CONFIG_GLOBAL} = ${json}; ` +
    `if (typeof window.${START_GLOBAL} === "function") window.${START_GLOBAL}(window.${CONFIG_GLOBAL}); true;`
  );
}

/**
 * The page's own script: `start` (a function expression) runs once, with the
 * first data to arrive, whether that came before this script ran or after.
 */
export function previewPageStartScript(start: string): string {
  return `(function () {
  var start = ${start};
  var started = false;
  function begin(config) {
    if (started || !config) return;
    started = true;
    start(config);
  }
  window.${START_GLOBAL} = begin;
  begin(window.${CONFIG_GLOBAL});
})();`;
}
