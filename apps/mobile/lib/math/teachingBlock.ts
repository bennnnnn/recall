/** Server-owned teaching pictures. The client draws the spec and does not recompute it. */

export type TeachingSpec = {
  type: string;
  answer: string;
  speech: string;
  [key: string]: unknown;
};

const TYPES = new Set([
  "place_value",
  "number_bond",
  "ten_frame",
  "array",
  "number_line_move",
  "fraction_bar",
  "fraction_line",
  "decimal_compare",
  "rounding",
  "polynomial_division",
  "unit_circle",
  "box_plot",
  "frequency_table",
  "stem_leaf",
  "histogram",
  "scatter",
  "probability_tree",
  "transformation",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

export function parseTeaching(raw: string): TeachingSpec | null {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isRecord(data) || typeof data.type !== "string" || !TYPES.has(data.type)) return null;
  if (typeof data.answer !== "string" || typeof data.speech !== "string" || !data.speech.trim()) {
    return null;
  }
  return data as TeachingSpec;
}

export function teachingSpeech(raw: string): string | null {
  return parseTeaching(raw)?.speech ?? null;
}
