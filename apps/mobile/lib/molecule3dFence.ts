/** Parse ```molecule3d / ```mol3d / ```3dmol fence bodies. */

export const MAX_SDF_LENGTH = 50000;

export type Molecule3DFence = {
  /** SDF (MOL block) string for 3Dmol.js rendering. */
  sdf: string;
  caption: string | null;
};

/**
 * Extract an SDF/MOL block from fence content.
 * Supports an optional plain-text caption on preceding lines.
 *
 * An SDF block starts with a molecule title line, then a line with
 * counts (e.g. "  9  9  0  0  0  0  0  0  0  0999 V2000"), and ends
 * with "M  END". We detect the block by finding "M  END" and taking
 * everything from the line that looks like the counts line upward.
 */
export function parseMolecule3DFence(content: string): Molecule3DFence | null {
  const raw = content.trim();
  if (!raw) return null;

  // Find "M  END" — the SDF block terminator.
  const endIdx = raw.indexOf("M  END");
  if (endIdx === -1) return null;

  const block = raw.slice(0, endIdx + 6); // include "M  END"
  if (block.length > MAX_SDF_LENGTH) return null;

  // The caption is any text after "M  END" (or before the block if no
  // trailing text). In practice the model puts the caption first, then
  // the SDF. We take lines before the counts line as the caption.
  const lines = block.split("\n");
  // The counts line is the 4th line in a MOL block (1-indexed: title,
  // program/timestamp, comment, counts). But the model may not include
  // all 3 header lines. Find the counts line by pattern.
  let countsLineIdx = -1;
  for (let i = 0; i < lines.length; i++) {
    // V2000 counts line: "  9  9  0  0  0  0  0  0  0  0999 V2000"
    // 11 integer fields + version. Be lenient on spacing/field count.
    if (/^\s*\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+V2000/.test(lines[i])) {
      countsLineIdx = i;
      break;
    }
    // V3000 counts line: "M  V30 BEGIN CTAB"
    if (/^M\s+V30\s+BEGIN\s+CTAB/.test(lines[i])) {
      countsLineIdx = i;
      break;
    }
  }

  let caption: string | null = null;
  if (countsLineIdx >= 3) {
    // Standard MOL block: title is line 0, program line 1, comment line 2.
    const title = lines[0].trim();
    if (title) caption = title;
  } else if (countsLineIdx > 0) {
    // Non-standard header — take any non-empty line before the counts line.
    const captionLines = lines.slice(0, countsLineIdx).filter((l) => l.trim().length > 0);
    if (captionLines.length > 0) {
      caption = captionLines[0].trim() || null;
    }
  }

  return { sdf: block, caption };
}
