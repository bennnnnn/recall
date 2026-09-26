/** Parse ```smiles / ```chemistry fence bodies into a SMILES string + optional caption. */

export const MAX_SMILES_LENGTH = 500;

/** Conservative SMILES charset (organic subset + common extensions). */
const SMILES_LINE =
  /^[A-Za-z0-9@+\-\[\]\(\)=#$/:\\.>%!~,*]+$/;

/** Formulas the model writes as SMILES (`H2`) — ring-closure syntax, not diatomics. */
const DIATOMIC_SMILES: Record<string, string> = {
  "H-H": "[H][H]",
  H2: "[H][H]",
  O2: "O=O",
  N2: "N#N",
  F2: "FF",
  Cl2: "ClCl",
  Br2: "BrBr",
  I2: "II",
};

function normalizeSmilesLine(raw: string): string {
  return DIATOMIC_SMILES[raw] ?? raw;
}

/** Element token for structure-formula detection (not full SMILES). */
// An *unbracketed* atom is restricted to SMILES' organic subset (plus H, which
// `DIATOMIC_SMILES` brackets on the way out). That is the spec, not a guess:
// every other element must be written `[W]`, so a bare `W` was never valid
// SMILES — which is exactly why RDKit answered "Could not render that
// structure" when a physics reply's `W = F d` arrived here as a molecule.
//
// `[A-Z][a-z]?` accepted any capital, so W (work), P (power), F (force) and T
// (tension) all read as elements, and a collapsed `F d` read as the element
// "Fd". Narrowing to the subset rejects every one of those on the token itself.
const ORGANIC_SUBSET = String.raw`(?:Cl|Br|[BCNOPSFIH])`;
const ELEMENT_TOKEN = String.raw`(?:\[[A-Z][a-z]?[+\-]?\d*\]|${ORGANIC_SUBSET})`;
/** Bond between atoms in math-ish molecule formulas. */
const BOND_TOKEN = String.raw`(?:=|#|-|\\equiv|≡)`;
const STRUCTURE_FORMULA_RE = new RegExp(
  `^${ELEMENT_TOKEN}(?:\\s*${BOND_TOKEN}\\s*${ELEMENT_TOKEN})+$`,
);

/**
 * A bare ASCII bond with space around it is algebra, not chemistry.
 *
 * Chemists write `O=O`, `H-H`, `N#N` tight; `N = W` is an equation. The
 * organic-subset rule above catches most physics, but not a line whose letters
 * happen to be in the subset — `N = P`, say. Spacing separates those, and it
 * costs nothing real: the LaTeX and unicode triple bonds (`\equiv`, `≡`) need
 * their spaces and are deliberately not listed here.
 */
const SPACED_ASCII_BOND_RE = /\s[=#-]|[=#-]\s/;

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
    const smiles = normalizeSmilesLine(raw);
    const captionParts = lines.slice(0, i);
    const caption = captionParts.length > 0 ? captionParts.join(" ").trim() : null;
    return { smiles, caption: caption || null };
  }

  // Last resort: first line only if it still looks SMILES-ish (no spaces,
  // no prose, at least one bond/bracket/atom token). The drawer will reject
  // truly invalid SMILES, but we avoid surfacing English prose as a molecule.
  const fallback = lines[0].replace(/^smiles:\s*/i, "").trim();
  if (!fallback || fallback.length > MAX_SMILES_LENGTH) return null;
  if (/\s/.test(fallback)) return null;
  if (/[A-Z][a-z]/.test(fallback) && !/[\[\]\(\)=#\\/.]/.test(fallback)) return null;
  if (!SMILES_LINE.test(fallback)) return null;
  return { smiles: normalizeSmilesLine(fallback), caption: null };
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
  // Read the spacing before anything collapses it, and only on the bonds the
  // author actually typed as ASCII — the `\equiv` below becomes a `#` and
  // would look wrongly spaced if this ran after.
  if (SPACED_ASCII_BOND_RE.test(s)) return null;

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
  return normalizeSmilesLine(s);
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
