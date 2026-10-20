/**
 * A chart fence's body, read the way a model may have written it. A caption line
 * before the JSON (`x^2 over [-5, 5]`) or a `{"type":"line","series":[…]}` chart
 * instead of Vega-Lite drew "JSON Parse error" in the bubble; both now draw.
 */

type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** The JSON in a chart body, or null. Lines of prose around the object are dropped. */
export function parseChartBody(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    const open = raw.indexOf("{");
    const close = raw.lastIndexOf("}");
    if (open === -1 || close <= open) return null;
    try {
      return JSON.parse(raw.slice(open, close + 1));
    } catch {
      return null;
    }
  }
}

const SERIES_MARKS: Record<string, string> = {
  line: "line",
  bar: "bar",
  area: "area",
  scatter: "point",
  point: "point",
};

/** A point as `[x, y]` or `{ "x": …, "y": … }`. */
function readPoint(point: unknown): [number, number] | null {
  const pair = Array.isArray(point) ? point : isRecord(point) ? [point.x, point.y] : null;
  if (!pair || typeof pair[0] !== "number" || typeof pair[1] !== "number") return null;
  return [pair[0], pair[1]];
}

function text(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

/**
 * `{"type", "title", "xLabel", "yLabel", "series": [{"name", "points": [[x, y], …]}]}` as
 * Vega-Lite. Null for anything else: a real Vega or Vega-Lite spec is left as written.
 */
export function seriesChartToVegaLite(spec: JsonRecord): JsonRecord | null {
  if ("mark" in spec || "layer" in spec || "$schema" in spec || "data" in spec) return null;
  const series = spec.series;
  if (!Array.isArray(series) || series.length === 0) return null;
  const values: { x: number; y: number; series: string }[] = [];
  for (const [index, line] of series.entries()) {
    if (!isRecord(line) || !Array.isArray(line.points)) return null;
    const name = text(line.name) ?? `Series ${index + 1}`;
    for (const point of line.points) {
      const read = readPoint(point);
      if (!read) return null;
      values.push({ x: read[0], y: read[1], series: name });
    }
  }
  const mark = SERIES_MARKS[String(spec.type ?? "line").toLowerCase()] ?? "line";
  const title = text(spec.title);
  return {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    ...(title ? { title } : {}),
    data: { values },
    mark,
    encoding: {
      x: { field: "x", type: "quantitative", title: text(spec.xLabel) ?? "x" },
      y: { field: "y", type: "quantitative", title: text(spec.yLabel) ?? "y" },
      ...(series.length > 1 ? { color: { field: "series", type: "nominal", title: null } } : {}),
    },
  };
}
