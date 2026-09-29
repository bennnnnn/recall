/** Read a parsed math tree aloud. Copy keeps its own serialization. */

import { parseSimpleLatex, type MathAccentKind, type MathSegment } from "@/lib/math/text";

const MAX_SPEAK_DEPTH = 12;

const SPOKEN_CHAR: Record<string, string> = {
  "=": "equals",
  "+": "plus",
  "-": "minus",
  "−": "minus",
  "±": "plus or minus",
  "∓": "minus or plus",
  "×": "times",
  "⋅": "dot",
  "·": "dot",
  "÷": "divided by",
  "/": "divided by",
  "<": "less than",
  ">": "greater than",
  "≤": "less than or equal to",
  "≥": "greater than or equal to",
  "≠": "not equal to",
  "≈": "approximately",
  "∞": "infinity",
  "→": "to",
  "←": "from",
  "⇒": "implies",
  "⇔": "if and only if",
  "α": "alpha",
  "β": "beta",
  "γ": "gamma",
  "δ": "delta",
  "ε": "epsilon",
  "ζ": "zeta",
  "η": "eta",
  "θ": "theta",
  "ι": "iota",
  "κ": "kappa",
  "λ": "lambda",
  "μ": "mu",
  "ν": "nu",
  "ξ": "xi",
  "π": "pi",
  "ρ": "rho",
  "σ": "sigma",
  "τ": "tau",
  "υ": "upsilon",
  "φ": "phi",
  "χ": "chi",
  "ψ": "psi",
  "ω": "omega",
  "Γ": "gamma",
  "Δ": "delta",
  "Θ": "theta",
  "Λ": "lambda",
  "Ξ": "xi",
  "Π": "pi",
  "Σ": "sigma",
  "Υ": "upsilon",
  "Φ": "phi",
  "Ψ": "psi",
  "Ω": "omega",
  "∂": "partial",
  "∇": "del",
  "∫": "integral",
  "∑": "sum",
  "′": "prime",
  "°": "degrees",
};

const FUNCTIONS: { name: string; spoken: string }[] = [
  { name: "arcsin", spoken: "arc sine" },
  { name: "arccos", spoken: "arc cosine" },
  { name: "arctan", spoken: "arc tangent" },
  { name: "sinh", spoken: "hyperbolic sine" },
  { name: "cosh", spoken: "hyperbolic cosine" },
  { name: "tanh", spoken: "hyperbolic tangent" },
  { name: "sin", spoken: "sine" },
  { name: "cos", spoken: "cosine" },
  { name: "tan", spoken: "tangent" },
  { name: "log", spoken: "log" },
  { name: "ln", spoken: "natural log" },
  { name: "exp", spoken: "exponential" },
  { name: "lim", spoken: "limit" },
  { name: "max", spoken: "max" },
  { name: "min", spoken: "min" },
  { name: "mod", spoken: "mod" },
  { name: "det", spoken: "determinant" },
];

function collapse(value: string): string {
  return value.replace(/\\[a-zA-Z]+/g, (command) => command.slice(1)).replace(/\s+/g, " ").trim();
}

function speakPlain(value: string, splitLetters: boolean): string {
  const pieces: string[] = [];
  let i = 0;
  while (i < value.length) {
    const ch = value[i] ?? "";
    if (ch === "\\") {
      const command = /^[a-zA-Z]+/.exec(value.slice(i + 1))?.[0];
      if (command) {
        pieces.push(command);
        i += command.length + 1;
        continue;
      }
      i += 1;
      continue;
    }
    if (ch === "{" || ch === "}" || ch === "(" || ch === ")" || ch === "[" || ch === "]" || ch === ",") {
      i += 1;
      continue;
    }
    if (/\s/.test(ch)) {
      i += 1;
      continue;
    }
    const named = SPOKEN_CHAR[ch];
    if (named) {
      pieces.push(named);
      i += 1;
      continue;
    }
    if (ch >= "0" && ch <= "9") {
      let j = i + 1;
      while (j < value.length && /[\d.]/.test(value[j] ?? "")) j += 1;
      pieces.push(value.slice(i, j));
      i = j;
      continue;
    }
    if (/[A-Za-z]/.test(ch)) {
      if (!splitLetters) {
        let j = i + 1;
        while (j < value.length && /[A-Za-z]/.test(value[j] ?? "")) j += 1;
        pieces.push(value.slice(i, j));
        i = j;
        continue;
      }
      const rest = value.slice(i);
      const fn = FUNCTIONS.find(
        (entry) => rest.startsWith(entry.name) && !/[A-Za-z]/.test(rest[entry.name.length] ?? ""),
      );
      if (fn) {
        pieces.push(fn.spoken);
        i += fn.name.length;
        continue;
      }
      pieces.push(ch);
      i += 1;
      continue;
    }
    i += 1;
  }
  return pieces.join(" ");
}

function speakScript(value: string, depth: number): string {
  if (depth >= MAX_SPEAK_DEPTH) return speakPlain(value, true);
  return speakSegments(parseSimpleLatex(value), depth + 1);
}

function sideIsNested(segments: MathSegment[]): boolean {
  return segments.some((segment) => segment.type === "frac" || segment.type === "sqrt");
}

function speakSide(segments: MathSegment[], depth: number): string {
  const spoken = speakSegments(segments, depth);
  return sideIsNested(segments) && spoken ? `the quantity ${spoken}` : spoken;
}

function speakSup(value: string, depth: number): string {
  const inner = speakScript(value, depth);
  if (inner === "2") return "squared";
  if (inner === "3") return "cubed";
  return inner ? `to the ${inner}` : "";
}

function speakAccent(kind: MathAccentKind, body: string): string {
  if (!body) return "";
  switch (kind) {
    case "vec":
    case "vecLeft":
      return `vector ${body}`;
    case "hat":
      return `${body} hat`;
    case "bar":
    case "overline":
      return `${body} bar`;
    case "tilde":
      return `${body} tilde`;
    case "dot":
      return `${body} dot`;
    case "ddot":
      return `${body} double dot`;
    case "underline":
      return `${body} underlined`;
  }
}

function speakSegment(segment: MathSegment, depth: number): string {
  switch (segment.type) {
    case "text":
      return speakPlain(segment.value, true);
    case "upright":
      return speakPlain(segment.value, false);
    case "sup":
      return speakSup(segment.value, depth);
    case "sub":
      return `sub ${speakScript(segment.value, depth)}`.trim();
    case "frac":
      return `${speakSide(segment.num, depth + 1)} over ${speakSide(segment.den, depth + 1)}`.trim();
    case "sqrt": {
      const body = speakSegments(segment.body, depth + 1);
      if (!segment.degree) return `square root of ${body}`.trim();
      const degree = speakScript(segment.degree, depth);
      if (degree === "3") return `cube root of ${body}`.trim();
      return `${degree} root of ${body}`.trim();
    }
    case "cancel":
      return speakSegments(segment.body, depth + 1);
    case "accent":
      return speakAccent(segment.kind, speakSegments(segment.body, depth + 1));
    default:
      return "";
  }
}

function speakSegments(segments: MathSegment[], depth: number): string {
  if (depth > MAX_SPEAK_DEPTH) return "";
  return collapse(segments.map((segment) => speakSegment(segment, depth)).filter(Boolean).join(" "));
}

export function speakMath(latex: string): string {
  return speakSegments(parseSimpleLatex(latex), 0);
}
