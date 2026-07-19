/** Parse ```smiles / ```chemistry fence bodies into a SMILES string + optional caption. */

export const MAX_SMILES_LENGTH = 500;

/** Conservative SMILES charset (organic subset + common extensions). */
const SMILES_LINE =
  /^[A-Za-z0-9@+\-\[\]\(\)=#$/:\\.>%!~,*]+$/;

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
