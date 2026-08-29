/**
 * Models often dump the series mean as a leftover ```answer / bare number
 * after a ```chart fence (Seattle rainfall → gray "3.1" pill). Chart turns
 * already told the model to stop after the fence; strip the crumb so stored
 * messages do not keep an AnswerBlock under the card.
 *
 * Linear fence walk (indexOf) — no nested regex.
 */
import { parseFenceLang } from "@/lib/codeHighlight";
import { isAnswerLang } from "@/lib/copyBlock";

const CHART_FENCE_LANGS = new Set(["chart", "vega", "vega-lite", "plot"]);

/** 3.1, -2, 50%, 5! — not "x = 2" or a recap sentence. */
const BARE_NUMBER_RE = /^[±+\-]?\d+(?:[.,]\d+)?(?:\s*[%])?!?$/;

export function isBareNumericChartCrumb(text: string): boolean {
  let s = text.trim();
  if (s.startsWith("**") && s.endsWith("**") && s.length >= 4) {
    s = s.slice(2, -2).trim();
  }
  while (s.startsWith("$") && s.endsWith("$") && s.length >= 2) {
    s = s.slice(1, -1).trim();
  }
  return BARE_NUMBER_RE.test(s);
}

function isCrumbFenceLang(lang: string): boolean {
  const l = lang.trim().toLowerCase();
  return l === "" || l === "math" || isAnswerLang(l);
}

function skipWs(src: string, from: number): number {
  let k = from;
  while (k < src.length) {
    const ch = src[k];
    if (ch === " " || ch === "\t" || ch === "\n" || ch === "\r") {
      k += 1;
      continue;
    }
    break;
  }
  return k;
}

export function stripNumericAnswerAfterChart(src: string): string {
  let out = "";
  let i = 0;
  while (i < src.length) {
    const open = src.indexOf("```", i);
    if (open === -1) {
      out += src.slice(i);
      break;
    }
    out += src.slice(i, open);
    const afterOpen = open + 3;
    const nl = src.indexOf("\n", afterOpen);
    if (nl === -1) {
      out += src.slice(open);
      break;
    }
    const lang = parseFenceLang(src.slice(afterOpen, nl));
    const close = src.indexOf("```", nl + 1);
    if (close === -1) {
      out += src.slice(open);
      break;
    }
    out += src.slice(open, close + 3);
    i = close + 3;
    if (!CHART_FENCE_LANGS.has(lang)) continue;

    const k = skipWs(src, i);
    if (k >= src.length) continue;

    if (src.startsWith("```", k)) {
      const crumbNl = src.indexOf("\n", k + 3);
      if (crumbNl === -1) continue;
      const crumbLang = parseFenceLang(src.slice(k + 3, crumbNl));
      const crumbClose = src.indexOf("```", crumbNl + 1);
      if (crumbClose === -1) continue;
      const body = src.slice(crumbNl + 1, crumbClose).trim();
      if (isCrumbFenceLang(crumbLang) && isBareNumericChartCrumb(body)) {
        i = crumbClose + 3;
      }
      continue;
    }

    const lineEnd = src.indexOf("\n", k);
    const line = (lineEnd === -1 ? src.slice(k) : src.slice(k, lineEnd)).trim();
    if (isBareNumericChartCrumb(line)) {
      i = lineEnd === -1 ? src.length : lineEnd + 1;
    }
  }
  return out;
}
