/** Parse ```smiles / ```chemistry fence bodies into a SMILES string + optional caption. */

export const MAX_SMILES_LENGTH = 500;

/** Conservative SMILES charset (organic subset + common extensions). */
const SMILES_LINE =
  /^[A-Za-z0-9@+\-\[\]\(\)=#$/:\\.>%!~,*]+$/;

/** Element token for structure-formula detection (not full SMILES). */
const ELEMENT_TOKEN = String.raw`(?:\[[A-Z][a-z]?[+\-]?\d*\]|[A-Z][a-z]?)`;
/** Bond between atoms in math-ish molecule formulas. */
const BOND_TOKEN = String.raw`(?:=|#|-|\\equiv|≡)`;
const STRUCTURE_FORMULA_RE = new RegExp(
  `^${ELEMENT_TOKEN}(?:\\s*${BOND_TOKEN}\\s*${ELEMENT_TOKEN})+$`,
);

/** Real math / LaTeX that must never be retagged as chemistry. */
const MATH_REJECT_RE =
  /\\(?:frac|sqrt|sum|int|prod|lim|begin|text|mathrm|left|right)|[\^_]|[=]=|[a-z]\s*=|=\s*[a-z]|\d\s*[+\-*/]\s*\d/;

export type ChemistryFence = {
  smiles: string;
  caption: string | null;
};

/**
 * Extract a single SMILES line from fence content.
 * Supports an optional plain-text caption on preceding lines.
 */
export function parseChemistryFence(content: string): ChemistryFence | null {
  const lines = content
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith("#"));
  if (lines.length === 0) return null;

  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const raw = lines[i].replace(/^smiles:\s*/i, "").trim();
    if (raw.length === 0 || raw.length > MAX_SMILES_LENGTH) continue;
    if (!SMILES_LINE.test(raw)) continue;
    const captionParts = lines.slice(0, i);
    const caption = captionParts.length > 0 ? captionParts.join(" ").trim() : null;
    return { smiles: raw, caption: caption || null };
  }

  // Last resort: first line even if charset is unusual (drawer will reject).
  const fallback = lines[0].replace(/^smiles:\s*/i, "").trim();
  if (!fallback || fallback.length > MAX_SMILES_LENGTH) return null;
  return { smiles: fallback, caption: null };
}

/**
 * Normalize a math-ish molecule formula (e.g. `N \equiv N`) to SMILES (`N#N`).
 * Returns null when the string is not a simple bonded structure formula.
 */
export function normalizeMoleculeFormulaToSmiles(raw: string): string | null {
  let s = raw.trim();
  if (!s || s.length > 80) return null;
  if (MATH_REJECT_RE.test(s)) return null;

  const double = s.match(/^\$\$([\s\S]+)\$\$$/);
  if (double) s = double[1].trim();
  else {
    const single = s.match(/^\$([^$\n]+)\$$/);
    if (single) s = single[1].trim();
  }
  if (!s || MATH_REJECT_RE.test(s)) return null;

  // Collapse LaTeX/unicode triple bonds and whitespace around bonds.
  s = s
    .replace(/\\equiv/gi, "#")
    .replace(/≡/g, "#")
    .replace(/\s*([=#\-])\s*/g, "$1")
    .replace(/\s+/g, "");

  if (!STRUCTURE_FORMULA_RE.test(s)) return null;
  if (!SMILES_LINE.test(s) || s.length > MAX_SMILES_LENGTH) return null;
  // Need at least one explicit bond (avoid bare "CO" / "NO" false positives).
  if (!/[=#\-]/.test(s)) return null;
  return s;
}

/** True when fence/math body should render as a Molecule card, not KaTeX. */
export function looksLikeMoleculeStructureFormula(raw: string): boolean {
  return normalizeMoleculeFormulaToSmiles(raw) != null;
}

/**
 * Retag molecule-like ```math / bare fences and whole-line `$...$` / `$$...$$`
 * into ```smiles so O₂ and N₂ share the same Molecule card style.
 */
export function retagMoleculeMathToSmiles(content: string): string {
  let out = content;

  out = out.replace(
    /```(math|latex|tex)?\s*\n([\s\S]*?)```/gi,
    (full, lang: string | undefined, body: string) => {
      const info = (lang ?? "").trim().toLowerCase();
      // Only touch untagged, math, latex, or tex fences.
      if (info && info !== "math" && info !== "latex" && info !== "tex") {
        return full;
      }
      const trimmed = body.trim();
      const lines = trimmed
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
      if (lines.length === 0 || lines.length > 2) return full;

      const smilesLine = normalizeMoleculeFormulaToSmiles(lines[lines.length - 1]);
      if (!smilesLine) return full;

      // Optional plain caption on the preceding line (no math cmds).
      if (lines.length === 2) {
        const caption = lines[0];
        if (MATH_REJECT_RE.test(caption) || /[=#$\\]/.test(caption)) return full;
        return `\`\`\`smiles\n${caption}\n${smilesLine}\n\`\`\``;
      }
      return `\`\`\`smiles\n${smilesLine}\n\`\`\``;
    },
  );

  // Whole-line display/inline math that is only a structure formula.
  out = out.replace(
    /^[ \t]*(?:\$\$([^$\n]+)\$\$|\$([^$\n]+)\$)[ \t]*$/gm,
    (full, display: string | undefined, inline: string | undefined) => {
      const smiles = normalizeMoleculeFormulaToSmiles((display ?? inline ?? "").trim());
      if (!smiles) return full;
      return `\`\`\`smiles\n${smiles}\n\`\`\``;
    },
  );

  return out;
}
