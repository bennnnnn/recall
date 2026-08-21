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

  if (countsLineIdx < 0) return null;

  // A V2000 MOL block has exactly 3 header lines before the counts line.
  // The backend used to prepend the formula (`O2\n` + RDKit molblock), which
  // shifted counts off line 4 and 3Dmol.js parsed 0 atoms — blank viewer.
  const headerStart = Math.max(0, countsLineIdx - 3);
  const prefix = lines
    .slice(0, headerStart)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
  const molLines = lines.slice(headerStart);
  const headerCount = countsLineIdx - headerStart;
  const padded =
    headerCount >= 3 ? molLines : [...Array<string>(3 - headerCount).fill(""), ...molLines];
  const sdf = `${padded.join("\n")}\n$$$$`;

  const trailing = raw.slice(endIdx + 6).trim();
  const title = padded[0]?.trim() || "";
  const caption = prefix[0] || trailing.split("\n")[0]?.trim() || title || null;

  return { sdf, caption };
}

export type MolAtom = { x: number; y: number; z: number; el: string };
export type MolBond = { a: number; b: number; order: number };
export type MolGeometry = { atoms: MolAtom[]; bonds: MolBond[] };

const ATOM_LINE_RE =
  /^\s*(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+([A-Z][a-z]?)/;
const BOND_LINE_RE = /^\s*(\d+)\s+(\d+)\s+(\d+)/;
const MAX_ATOMS = 400;

/**
 * Read 3D atom positions and bonds from a V2000 MOL/SDF block.
 * Used by the native SVG viewer (WebGL/3Dmol.js is unreliable in WKWebView).
 */
export function parseMolGeometry(sdf: string): MolGeometry | null {
  const lines = sdf.split("\n");
  let countsIdx = -1;
  for (let i = 0; i < lines.length; i++) {
    if (
      /V2000/.test(lines[i]!) &&
      /^\s*\d+\s+\d+/.test(lines[i]!)
    ) {
      countsIdx = i;
      break;
    }
  }
  if (countsIdx < 0) return null;
  const parts = lines[countsIdx]!.trim().split(/\s+/);
  const nAtoms = Number.parseInt(parts[0] ?? "", 10);
  const nBonds = Number.parseInt(parts[1] ?? "", 10);
  if (!Number.isFinite(nAtoms) || nAtoms < 1 || nAtoms > MAX_ATOMS) return null;
  if (!Number.isFinite(nBonds) || nBonds < 0) return null;

  const atoms: MolAtom[] = [];
  for (let i = 0; i < nAtoms; i++) {
    const line = lines[countsIdx + 1 + i];
    if (!line) return null;
    const m = line.match(ATOM_LINE_RE);
    if (!m) return null;
    atoms.push({ x: Number(m[1]), y: Number(m[2]), z: Number(m[3]), el: m[4]! });
  }

  const bonds: MolBond[] = [];
  for (let i = 0; i < nBonds; i++) {
    const line = lines[countsIdx + 1 + nAtoms + i];
    if (!line) break;
    const m = line.match(BOND_LINE_RE);
    if (!m) continue;
    const a = Number(m[1]) - 1;
    const b = Number(m[2]) - 1;
    const order = Number(m[3]) || 1;
    if (a >= 0 && b >= 0 && a < nAtoms && b < nAtoms && a !== b) {
      bonds.push({ a, b, order });
    }
  }
  return { atoms, bonds };
}
