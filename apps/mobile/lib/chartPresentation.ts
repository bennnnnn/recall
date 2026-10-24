/**
 * How a chart spec is laid out for a phone card, decided on the phone each time a chart
 * draws, so a reply stored before a fix draws with it too. Every rule fills in only what
 * the spec left unset; an explicit sort, scale, axis format or legend stays as written.
 *
 * - Named categories go on y (bars), in the order the data gives them.
 * - Colour, fill and stroke categories keep the order the data gives them (legend, slices).
 * - Lines and points are not pinned to zero: 80 → 75 kg was a flat line along the top.
 * - Large numbers on a value axis are written short (12.5k, 4.1M, 7.8B): a 300 px card cut
 *   "4,000,000,000" to "4,000,000,0".
 * - A title longer than the card wraps: a wide title shrank the plot under it to fit beside it.
 * - Tooltips are dropped (the card shows none), and pre-binned bars get their bin end.
 */
import { isRecord, type JsonRecord } from "@/lib/chartSeriesSpec";

const COMPOSITE_KEYS = ["layer", "hconcat", "vconcat", "concat"] as const;
const BAND_PX = 28;
const BAND_HEIGHT_MIN = 120;
const BAND_HEIGHT_MAX = 280;
// Marks that read from where the data is, not from zero; rules and text ride along.
const UNPINNED_MARKS = new Set(["line", "point", "circle", "square", "trail"]);
const NEUTRAL_MARKS = new Set(["rule", "text", "tick"]);
const COLOR_CHANNELS = ["color", "fill", "stroke"] as const;
const LABEL_FORMAT_KEYS = ["format", "formatType", "labelExpr"];
// A bold 13 px title runs about 8 px a character.
const TITLE_PX_PER_CHAR = 8;

/**
 * An axis label written short: 12.5k from 1e4, 12.5M from 1e6, 4B from 1e9; smaller values as
 * Vega formats them. Given the axis's scale, the size of its largest end picks one unit for
 * every label on it (0, 5k, 10k, 15k rather than 0, 5,000, 10k, 15k).
 */
export function compactLabelExpr(scale: string | null): string {
  const size = scale ? `max(abs(domain('${scale}')[0]), abs(peek(domain('${scale}'))))` : "abs(datum.value)";
  return (
    `${size} >= 1e4 ? (datum.value === 0 ? '0' : ` +
    `${size} >= 1e9 ? format(datum.value / 1e9, '.4~r') + 'B' : ` +
    `${size} >= 1e6 ? format(datum.value / 1e6, '.4~r') + 'M' : ` +
    `format(datum.value / 1e3, '.4~r') + 'k') : datum.label`
  );
}

function markType(mark: unknown): string | undefined {
  if (typeof mark === "string") return mark;
  return isRecord(mark) && typeof mark.type === "string" ? mark.type : undefined;
}

function channelType(ch: unknown): string | undefined {
  return isRecord(ch) && typeof ch.type === "string" ? ch.type : undefined;
}

function isCategoryType(t: string | undefined): boolean {
  return t === "nominal" || t === "ordinal";
}

function applyNominalSort(encoding: JsonRecord, key: string): void {
  const chan = encoding[key];
  if (!isRecord(chan) || "sort" in chan) return;
  if (chan.type === "quantitative" || chan.type === "temporal") return;
  chan.sort = null;
}

/**
 * Named categories on x become unreadable on a phone (labels clip under the
 * plot). ChatGPT-shaped: months/items on y, values on x.
 */
function preferHorizontalCategoryBars(spec: JsonRecord): void {
  if (markType(spec.mark) !== "bar" || !isRecord(spec.encoding)) return;
  const enc = spec.encoding;
  if (!isCategoryType(channelType(enc.x)) || channelType(enc.y) !== "quantitative") return;
  [enc.x, enc.y] = [enc.y, enc.x];
  const xOff = enc.xOffset;
  const yOff = enc.yOffset;
  if (xOff !== undefined || yOff !== undefined) {
    enc.xOffset = yOff;
    enc.yOffset = xOff;
    if (enc.xOffset === undefined) delete enc.xOffset;
    if (enc.yOffset === undefined) delete enc.yOffset;
  }
}

function setHorizontalBandHeight(spec: JsonRecord): void {
  if (markType(spec.mark) !== "bar" || spec.height != null || !isRecord(spec.encoding)) return;
  if (!isCategoryType(channelType(spec.encoding.y))) return;
  const values = isRecord(spec.data) ? spec.data.values : undefined;
  const n = Array.isArray(values) ? values.length : 6;
  spec.height = Math.min(BAND_HEIGHT_MAX, Math.max(BAND_HEIGHT_MIN, n * BAND_PX));
}

/** The end field a spec's `bin` transform writes beside `start`, if it has one. */
function binEndField(spec: JsonRecord, start: unknown): string | undefined {
  const steps = Array.isArray(spec.transform) ? spec.transform : [];
  for (const step of steps) {
    if (!isRecord(step) || !("bin" in step)) continue;
    const as = step.as;
    if (Array.isArray(as) && as[0] === start && typeof as[1] === "string") return as[1];
    if (typeof as === "string" && as === start) return `${as}_end`;
  }
  return undefined;
}

/**
 * Bars a model pre-binned (`"bin": "binned"`) need the bin's end on x2 / y2; without
 * it Vega-Lite drew no bars at all. The end comes from the spec's own bin transform,
 * or the channel draws plain bars at each bin's start.
 */
function pairBinnedEdges(spec: JsonRecord, enc: JsonRecord): void {
  for (const axis of ["x", "y"] as const) {
    const ch = enc[axis];
    if (!isRecord(ch) || ch.bin !== "binned" || enc[`${axis}2`] !== undefined) continue;
    const end = binEndField(spec, ch.field);
    if (end) enc[`${axis}2`] = { field: end };
    else delete ch.bin;
  }
}

function normalizeUnit(spec: JsonRecord): void {
  preferHorizontalCategoryBars(spec);
  if (isRecord(spec.encoding)) {
    const enc = spec.encoding;
    applyNominalSort(enc, "x");
    applyNominalSort(enc, "y");
    // The card shows no tooltips, and a tooltip's bad format string threw inside
    // Vega's dataflow and left the chart blank.
    delete enc.tooltip;
    pairBinnedEdges(spec, enc);
  }
  setHorizontalBandHeight(spec);
}

/** Every view in a spec, with whether it is one layer of a layered plot. */
function eachView(spec: JsonRecord, visit: (view: JsonRecord, inLayer: boolean) => void, inLayer = false): void {
  visit(spec, inLayer);
  for (const key of COMPOSITE_KEYS) {
    const kids = spec[key];
    if (!Array.isArray(kids)) continue;
    for (const kid of kids) if (isRecord(kid)) eachView(kid, visit, inLayer || key === "layer");
  }
  if (isRecord(spec.spec)) eachView(spec.spec, visit);
}

/** Layout + category order for a Vega-Lite spec (mutates). */
export function normalizeChartSpec(spec: JsonRecord): void {
  eachView(spec, (view) => normalizeUnit(view));
}

/** Whether a channel holds categories: said so, or a plain field Vega-Lite reads as nominal. */
function holdsCategories(ch: JsonRecord): boolean {
  const type = channelType(ch);
  if (type !== undefined) return isCategoryType(type);
  return "field" in ch && !["aggregate", "bin", "timeUnit"].some((key) => key in ch);
}

/** A nominal colour, fill or stroke with no sort keeps the data's order. */
function keepColorOrder(view: JsonRecord): void {
  if (!isRecord(view.encoding)) return;
  for (const key of COLOR_CHANNELS) {
    const ch = view.encoding[key];
    if (isRecord(ch) && holdsCategories(ch) && !("sort" in ch)) ch.sort = null;
  }
}

/** The marks a plot draws: its own, or every layer's. */
function plotMarks(view: JsonRecord): string[] {
  if (Array.isArray(view.layer)) return view.layer.flatMap((kid) => (isRecord(kid) ? plotMarks(kid) : []));
  const mark = markType(view.mark);
  return mark ? [mark] : [];
}

function plotEncodings(view: JsonRecord): JsonRecord[] {
  const own = isRecord(view.encoding) ? [view.encoding] : [];
  const kids = Array.isArray(view.layer) ? view.layer.filter(isRecord) : [];
  return [...own, ...kids.flatMap(plotEncodings)];
}

/** Said to be quantitative, or a count, sum or bin Vega-Lite reads as one. */
function isQuantitative(ch: JsonRecord): boolean {
  if (ch.type !== undefined) return ch.type === "quantitative";
  return typeof ch.aggregate === "string" || Boolean(ch.bin);
}

function unpinFromZero(ch: unknown): void {
  if (!isRecord(ch) || ch.bin || ch.scale === null || !isQuantitative(ch)) return;
  const scale = isRecord(ch.scale) ? ch.scale : {};
  if (["zero", "domain", "domainMin", "domainMax"].some((key) => key in scale)) return;
  ch.scale = { ...scale, zero: false };
}

/** A line or scatter plot's quantitative axes start where the data does, not at zero. */
function unpinLines(view: JsonRecord, inLayer: boolean): void {
  if (inLayer) return;
  const marks = plotMarks(view);
  if (!marks.some((mark) => UNPINNED_MARKS.has(mark))) return;
  if (!marks.every((mark) => UNPINNED_MARKS.has(mark) || NEUTRAL_MARKS.has(mark))) return;
  for (const encoding of plotEncodings(view)) {
    unpinFromZero(encoding.x);
    unpinFromZero(encoding.y);
  }
}

function setsLabelFormat(block: unknown): boolean {
  return isRecord(block) && LABEL_FORMAT_KEYS.some((key) => key in block);
}

/** Whether the spec's config formats axis labels for every axis. */
function configFormatsLabels(spec: JsonRecord): boolean {
  const config = isRecord(spec.config) ? spec.config : {};
  if ("numberFormat" in config) return true;
  return Object.entries(config).some(([key, block]) => key.startsWith("axis") && setsLabelFormat(block));
}

/**
 * Each value axis with no format of its own writes large numbers short. In one plot (a unit
 * or layered spec) an axis's scale is named after its channel; elsewhere each label is sized alone.
 */
function compactAxisLabels(spec: JsonRecord): void {
  if (configFormatsLabels(spec)) return;
  const encoding = isRecord(spec.encoding) ? spec.encoding : {};
  const faceted = ["row", "column", "facet"].some((key) => key in encoding);
  const onePlot = ("mark" in spec || "layer" in spec) && !("resolve" in spec) && !faceted;
  eachView(spec, (view) => {
    if (!isRecord(view.encoding)) return;
    for (const key of ["x", "y"] as const) {
      const ch = view.encoding[key];
      if (!isRecord(ch) || !isQuantitative(ch) || ch.axis === null) continue;
      const axis = isRecord(ch.axis) ? ch.axis : {};
      // A log scale's ticks span powers of ten: one unit for the axis drew "0.001k … 100k".
      const logScale = isRecord(ch.scale) && ["log", "symlog"].includes(String(ch.scale.type));
      const sized = onePlot && !logScale ? key : null;
      if (!setsLabelFormat(axis)) ch.axis = { ...axis, labelExpr: compactLabelExpr(sized) };
    }
  });
}

/** Words as lines of at most `chars` characters (a longer word keeps a line to itself). */
function wrapWords(text: string, chars: number): string[] {
  const lines: string[] = [];
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const last = lines[lines.length - 1];
    if (last !== undefined && last.length + 1 + word.length <= chars) lines[lines.length - 1] = `${last} ${word}`;
    else lines.push(word);
  }
  return lines;
}

/** A title wider than the card as lines that fit it. */
function wrapTitle(spec: JsonRecord, width: number): void {
  const chars = Math.max(16, Math.floor(width / TITLE_PX_PER_CHAR));
  const title = spec.title;
  if (typeof title === "string" && title.length > chars) spec.title = wrapWords(title, chars);
  else if (isRecord(title) && typeof title.text === "string" && title.text.length > chars) {
    title.text = wrapWords(title.text, chars);
  }
}

// A slice too thin to hold its share: no label (the legend still names it).
const SLICE_LABEL_MIN_SHARE = 0.05;

/**
 * A pie or donut with each slice's share written on it: the slices told no numbers, and a
 * budget pie could not be read. The arc and its label share the stacked angle, so each label
 * sits mid-slice. The field reaches the expression only as a JSON string literal.
 */
function labelSlices(spec: JsonRecord): JsonRecord {
  const mark = spec.mark;
  const encoding = isRecord(spec.encoding) ? spec.encoding : null;
  const theta = encoding && isRecord(encoding.theta) ? encoding.theta : null;
  if (markType(mark) !== "arc" || "layer" in spec || !encoding || !theta) return spec;
  const field = theta.field;
  if (typeof field !== "string" || /[.[\]]/.test(field) || "aggregate" in theta || "text" in encoding) return spec;
  const inner = isRecord(mark) && typeof mark.innerRadius === "number" ? mark.innerRadius : 0;
  const radius = inner ? `(min(width, height) / 2 + ${inner}) / 2` : "min(width, height) / 2 * 0.62";
  const value = `datum[${JSON.stringify(field)}]`;
  const share = `${value} / datum.__total`;
  const transform = Array.isArray(spec.transform) ? spec.transform : [];
  return {
    ...spec,
    mark: undefined,
    transform: [
      ...transform,
      { joinaggregate: [{ op: "sum", field, as: "__total" }] },
      { calculate: `${share} >= ${SLICE_LABEL_MIN_SHARE} ? format(${share}, '.0%') : ''`, as: "__share" },
    ],
    encoding: { ...encoding, theta: { ...theta, stack: true } },
    layer: [
      { mark },
      {
        mark: { type: "text", radius: { expr: radius }, fill: "#ffffff", fontWeight: "bold", fontSize: 12 },
        encoding: { text: { field: "__share", type: "nominal" } },
      },
    ],
  };
}

function isVegaSpec(spec: JsonRecord): boolean {
  return typeof spec.$schema === "string" && spec.$schema.includes("/schema/vega/");
}

/** The spec as a card `width` px wide draws it: a laid-out copy, the given spec untouched. */
export function presentChartSpec(spec: JsonRecord, width = 320): JsonRecord {
  const parsed = JSON.parse(JSON.stringify(spec)) as JsonRecord;
  if (isVegaSpec(parsed)) return parsed;
  const out = JSON.parse(JSON.stringify(labelSlices(parsed))) as JsonRecord;
  eachView(out, (view, inLayer) => {
    normalizeUnit(view);
    keepColorOrder(view);
    unpinLines(view, inLayer);
  });
  compactAxisLabels(out);
  wrapTitle(out, width);
  return out;
}
