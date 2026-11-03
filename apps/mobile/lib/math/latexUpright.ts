/**
 * What maths keeps upright, whoever wrote it: a unit after its number, a word of the
 * sentence, a chemical formula. A model writes `$M = 58.44g/mol$`, `$2H₂ : 2H₂O, so 1:1$`
 * and `$n(H₂O)$`; read as TeX every letter there is a symbol in the maths italic, so the
 * unit, the "so" and the formula came out as italic letters (live, 2026-11-02). Every
 * subject's maths goes through this one rule, inline and display alike, before either
 * renderer sees it:
 *
 * - a unit after a number: `58.44g/mol` → `58.44\,\mathrm{g/mol}` (a compound or longer
 *   unit even glued to it; one letter only after a space and at the end of a value, so
 *   `5m` and `2x` stay algebra);
 * - a word of the sentence between spaces (`so`, `and`, `per`, `therefore`) →
 *   `\text{ so }`; `at` is never one (`v = u + at`);
 * - a formula written with Unicode counts or a charge (`H₂O`, `Fe²⁺`) → `\mathrm{H₂O}`,
 *   drawn as written; `C₁V₁` and `V₂` are symbols, not formulas.
 *
 * What is already upright (`\mathrm{…}`, `\text{…}`) and every script group is left as
 * written. The server lays out its own rows this way (`modules/chemistry/tex.py`).
 */
import { readGroup } from "@/lib/math/latexGroups";

const ELEMENTS = new Set(
  (
    "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As " +
    "Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu " +
    "Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np " +
    "Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og"
  ).split(" "),
);
const MOLECULAR = new Set(["H₂", "N₂", "O₂", "F₂", "Cl₂", "Br₂", "I₂", "O₃", "P₄", "S₈"]);

const UNIT_ATOMS = (
  "mmHg kcal mmol µmol mol kPa MPa MeV keV eV kHz MHz Hz kJ MJ kW MW kWh cal atm bar Pa torr " +
  "min ms µs ns mL µL dL kg mg µg km cm mm µm nm mV kV mA °C °F K g L J s h m N W V A Ω M"
)
  .split(" ")
  .sort((a, b) => b.length - a.length);
const ATOM = UNIT_ATOMS.map((atom) => atom.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
const POWER = String.raw`(?:\^\{?-?\d\}?|⁻?[¹²³])?`;
const GROUP = `(?:${ATOM})${POWER}(?:·(?:${ATOM})${POWER})*`;
const UNIT_RE = new RegExp(String.raw`^(?:${GROUP})(?:/(?:\((?:${GROUP})\)|${GROUP}))*(?![A-Za-z°µΩ])`);
// After the unit: the end of the value.
const VALUE_END = /^(?:$|[\s,;.)\]=+\-−]|\\[,;:! ]|\\(?:quad|qquad|text))/;

const WORDS = new Set(
  (
    "so and or then thus hence since because therefore with per of for is are gives when " +
    "where if not the to from by which that"
  ).split(" "),
);

// A charge is never followed by a superscript digit: in K⁻¹ the ⁻ is an exponent's sign.
const FORMULA_RE = /^(?:\(?(?:[A-Z][a-z]?[₀-₉]*)+\)?[₀-₉]*)+[⁰¹²³⁴⁵⁶⁷⁸⁹]*(?:[⁺⁻](?![⁰¹²³⁴⁵⁶⁷⁸⁹]))?/;
const NUMBER_RE = /^\d+(?:\.\d+)?/;
const POWER_OF_TEN_END = /10\^\{?-?\d+\}?$/;

/** A formula as written with Unicode counts or a charge, never a numbered symbol. */
function isFormula(token: string, indexed: boolean): boolean {
  const charge = /[⁰¹²³⁴⁵⁶⁷⁸⁹]*[⁺⁻]$/.exec(token)?.[0] ?? "";
  const body = token.slice(0, token.length - charge.length);
  const letters = body.match(/[A-Z][a-z]?/g) ?? [];
  if (letters.length === 0 || !letters.every((symbol) => ELEMENTS.has(symbol))) return false;
  if (body.replace(/[A-Z][a-z]?|[₀-₉]|[()]/g, "") !== "") return false;
  if (charge) return true;
  const counts: string[] = body.match(/[₀-₉]+/g) ?? [];
  if (counts.length === 0 || counts.includes("₁")) return false;
  // Beside C₁V₁, C₂V₂ is the same symbols numbered two, not a compound.
  if (indexed && new Set(counts).size === 1 && counts[0]!.length === 1) return false;
  return letters.length > 1 || MOLECULAR.has(body);
}

/** A formula without a closing bracket it never opened: `H₂O` of `n(H₂O)`. */
function balanced(token: string | undefined): string | undefined {
  if (!token) return token;
  let text = token;
  while (text.endsWith(")") && (text.match(/\(/g) ?? []).length < (text.match(/\)/g) ?? []).length) {
    text = text.slice(0, -1);
  }
  return text;
}

function unitTex(unit: string): string {
  if (unit.startsWith("°") && unit.length > 1) return String.raw`\,^\circ\mathrm{${unit.slice(1)}}`;
  const power = /(\^\{?-?\d\}?)$/.exec(unit)?.[1];
  const body = power ? unit.slice(0, -power.length) : unit;
  return String.raw`\,\mathrm{${body}}` + (power ? `^{${power.replace(/[\^{}]/g, "")}}` : "");
}

/** The unit read straight after a number at `at`, or null. */
function unitAfter(source: string, at: number): { tex: string; next: number } | null {
  const spaced = source[at] === " ";
  const start = spaced ? at + 1 : at;
  const match = UNIT_RE.exec(source.slice(start));
  if (!match) return null;
  const unit = match[0];
  const next = start + unit.length;
  const compound = /[/·]/.test(unit) || unit.replace(/\^.*|[⁻¹²³]/g, "").length > 1;
  if (!spaced && !compound) return null;
  if (!compound && !VALUE_END.test(source.slice(next))) return null;
  return { tex: unitTex(unit), next };
}

/** `source` with its units, sentence words and formulas upright. */
export function uprightNotation(source: string): string {
  const indexed = /[A-Z][a-z]?₁(?![₀-₉])/.test(source);
  let out = "";
  let i = 0;
  while (i < source.length) {
    const char = source[i]!;
    if (char === "\\") {
      const name = /^\\([A-Za-z]+)/.exec(source.slice(i))?.[1];
      if (!name) {
        out += source.slice(i, i + 2);
        i += 2;
        continue;
      }
      out += `\\${name}`;
      i += name.length + 1;
      // Words and units already upright stay exactly as written.
      if (/^(?:text\w*|mathrm|operatorname|mbox|ce|pu)$/.test(name)) {
        const group = source[i] === "{" ? readGroup(source, i) : null;
        if (group) {
          out += source.slice(i, group.next);
          i = group.next;
        }
      }
      continue;
    }
    if (char === "^" || char === "_") {
      const group = source[i + 1] === "{" ? readGroup(source, i + 1) : null;
      const next = group ? group.next : i + 2;
      out += source.slice(i, next);
      i = next;
      // A power of ten ends a number too: `6.022 \times 10^{23} mol^{-1}`.
      const unit = POWER_OF_TEN_END.test(out) && source[i] === " " ? unitAfter(source, i) : null;
      if (unit) {
        out += unit.tex;
        i = unit.next;
      }
      continue;
    }
    const previous = source[i - 1] ?? "";
    if (/\d/.test(char) && !/[A-Za-z\d.]/.test(previous)) {
      const number = NUMBER_RE.exec(source.slice(i))![0];
      out += number;
      i += number.length;
      const unit = unitAfter(source, i);
      if (unit) {
        out += unit.tex;
        i = unit.next;
      }
      continue;
    }
    if (/[A-Za-z(]/.test(char) && !/[A-Za-z\\]/.test(previous)) {
      const word = /^[a-z]+/.exec(source.slice(i))?.[0];
      if (word && WORDS.has(word) && /\s/.test(previous) && /^\s/.test(source.slice(i + word.length))) {
        out = out.replace(/ +$/, "");
        out += String.raw`\text{ ${word} }`;
        i += word.length;
        while (source[i] === " ") i += 1;
        continue;
      }
      const formula = balanced(FORMULA_RE.exec(source.slice(i))?.[0]);
      if (formula && /[₀-₉⁺⁻]/.test(formula) && isFormula(formula, indexed)) {
        out += String.raw`\mathrm{${formula}}`;
        i += formula.length;
        continue;
      }
    }
    out += char;
    i += 1;
  }
  return out;
}
