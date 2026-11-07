/**
 * A plotted relation as LaTeX, for a graph's legend: `y = x^2 - 4*x + 3` reads as
 * y = x² − 4x + 3 in the maths face, not as the plotting grammar's raw text. Built from
 * the same parse the curve is sampled from (`graphExpr.ts`), so the legend names exactly
 * the curve drawn; a relation that grammar cannot read gets no LaTeX and keeps its text.
 */
import { parseGraphRelation, type GraphCmp, type GraphExprNode } from "@/lib/math/graphExpr";

/** Binding strength: a child weaker than its place needs brackets. */
const ADD = 1;
const MUL = 2;
const NEG = 3;
const POW = 4;
const ATOM = 5;

const CMP_LATEX: Record<GraphCmp, string> = { "=": "=", "<": "<", "<=": "\\le", ">": ">", ">=": "\\ge" };

/** Functions with a LaTeX name of their own; the rest are drawn upright by name. */
const NAMED: Record<string, string> = {
  sin: "\\sin", cos: "\\cos", tan: "\\tan",
  asin: "\\arcsin", acos: "\\arccos", atan: "\\arctan",
  sinh: "\\sinh", cosh: "\\cosh", tanh: "\\tanh",
  ln: "\\ln", log: "\\log", lg: "\\log", log10: "\\log",
};

type Drawn = { tex: string; strength: number };

function bracket(child: Drawn, strength: number): string {
  return child.strength < strength ? `(${child.tex})` : child.tex;
}

function number(v: number): string {
  return String(Number(v.toPrecision(12)));
}

function drawCall(name: string, arg: Drawn): Drawn {
  if (name === "sqrt") return { tex: `\\sqrt{${arg.tex}}`, strength: ATOM };
  if (name === "abs") return { tex: `|${arg.tex}|`, strength: ATOM };
  if (name === "exp") return { tex: `e^{${arg.tex}}`, strength: POW };
  if (name === "floor") return { tex: `\\lfloor ${arg.tex} \\rfloor`, strength: ATOM };
  if (name === "ceil") return { tex: `\\lceil ${arg.tex} \\rceil`, strength: ATOM };
  const head = NAMED[name] ?? `\\operatorname{${name}}`;
  return { tex: `${head}(${arg.tex})`, strength: ATOM };
}

/**
 * A product as written in school, its factors side by side: 4x, 2\sin(x), x(x − 1). A dot
 * only where side by side would read as one number (x · 2, 3 · 4) or a subtraction.
 */
function drawProduct(l: GraphExprNode, r: GraphExprNode, variable: string): Drawn {
  const left = bracket(draw(l, variable), MUL);
  const right = draw(r, variable);
  const dot = /^[\d.-]/.test(right.tex) || right.strength === NEG;
  // Spaces are drawn: none between factors, unless a command name would run on.
  const join = dot ? " \\cdot " : /\\[A-Za-z]+$/.test(left) ? " " : "";
  return { tex: `${left}${join}${bracket(right, dot ? POW : NEG)}`, strength: MUL };
}

function drawBinary(node: Extract<GraphExprNode, { t: "bin" }>, variable: string): Drawn {
  const { op, l, r } = node;
  if (op === "^") {
    return { tex: `${bracket(draw(l, variable), ATOM)}^{${draw(r, variable).tex}}`, strength: POW };
  }
  if (op === "/") {
    return { tex: `\\frac{${draw(l, variable).tex}}{${draw(r, variable).tex}}`, strength: ATOM };
  }
  if (op === "*") return drawProduct(l, r, variable);
  const right = draw(r, variable);
  // a − (b + c) and a + (−b) keep their brackets, as the parse read them.
  const needs = right.strength === NEG ? POW : op === "-" ? MUL : ADD;
  return { tex: `${draw(l, variable).tex} ${op} ${bracket(right, needs)}`, strength: ADD };
}

function draw(node: GraphExprNode, variable: string): Drawn {
  switch (node.t) {
    case "num":
      if (node.name === "pi") return { tex: "π", strength: ATOM };
      if (node.name) return { tex: node.name, strength: ATOM };
      return { tex: number(node.v), strength: node.v < 0 ? NEG : ATOM };
    case "var":
      return { tex: variable, strength: ATOM };
    case "unary":
      return { tex: `-${bracket(draw(node.arg, variable), MUL)}`, strength: NEG };
    case "call":
      return drawCall(node.name, draw(node.arg, variable));
    case "bin":
      return drawBinary(node, variable);
  }
}

/** `y = …` (or `y < …`) in LaTeX, or null when the plotting grammar cannot read `expr`. */
export function graphRelationLatex(expr: string, variable = "x"): string | null {
  const relation = parseGraphRelation(expr, variable);
  if (!relation) return null;
  return `y ${CMP_LATEX[relation.cmp]} ${draw(relation.node, variable).tex}`;
}
