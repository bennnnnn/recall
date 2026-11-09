/**
 * Chemical notation in prose stays as written: a SMILES string becomes inline code.
 *
 * "CN1C=NC2=C1C(=O)N(C(=O)N2C)C" read as maths ("C $=O$ N") here, and as an
 * a=b=c chain on the server. As inline code, every later pass leaves it alone.
 *
 * Twin of apps/api/app/modules/chat/notation_spans.py; docs/fixtures/presentation_cases.json
 * holds both to the same output.
 */
import { applyOutsideFences } from "@/lib/fence/scan";

const CHARSET = /^[A-Za-z0-9@+\-[\]()=#%/\\.]+$/;
const LETTERS = /[A-Za-z]+/g;
// Organic atoms, aromatic lowercase atoms, and two-letter element symbols. A capital takes the
// small letter after it ("Cl", "Br", "Bb"), so each run is read one way only: "B" then "b"
// as well as "Bb" made a long run of "Bb" take exponential time (CodeQL js/redos).
const ATOMS = /^(?:[A-Z][a-z]|[BCNOPSFIKH](?![a-z])|[bcnops])+$/;
const RING_ATOM = /(?:[A-Z][a-z]?|[cnosp])(\d)/g;
// Inline code and maths are left as they are; prose between them is read.
const PROTECTED = /(`+[^`\n]*`+|\$\$[\s\S]*?\$\$|\$[^$\n]+\$)/;
const TOKEN = /[^\s`$]+/g;
const TRAILING = ".,;:!?";
const MIN_LENGTH = 6;

/** True for a SMILES string such as `CC(=O)O` or `O=Cc1ccccc1`. */
function isNotation(token: string): boolean {
  if (
    token.length < MIN_LENGTH ||
    token.includes("://") ||
    token.includes("](")
  )
    return false;
  if (!CHARSET.test(token)) return false;
  const runs = token.match(LETTERS) ?? [];
  // "2(1.008)" has no atom at all; "F=ma" has a run that is not one.
  if (runs.length === 0 || runs.some((run) => !ATOMS.test(run))) return false;
  const rings = [...token.matchAll(RING_ATOM)].map((match) => match[1]);
  const branched = token.includes("(") || token.includes("[");
  const bonded = token.includes("=") || token.includes("#");
  return (
    (bonded || branched) && (branched || rings.length > new Set(rings).size)
  );
}

/** `raw` without trailing punctuation. A loop, like the twin's `rstrip`: `/[.,;:!?]+$/`
 * read a long run of dots again from each dot when the token did not end in one. */
function withoutTrailing(raw: string): string {
  let end = raw.length;
  while (end > 0 && TRAILING.includes(raw[end - 1])) end -= 1;
  return raw.slice(0, end);
}

function codeToken(raw: string): string {
  const token = withoutTrailing(raw);
  if (!isNotation(token)) return raw;
  return `\`${token}\`${raw.slice(token.length)}`;
}

function codeProse(prose: string): string {
  // split() keeps the protected spans at odd indexes.
  return prose
    .split(PROTECTED)
    .map((part, index) => (index % 2 ? part : part.replace(TOKEN, codeToken)))
    .join("");
}

/** Wrap each SMILES string in prose as inline code; fences, code and maths stay. */
export function codeNotation(text: string): string {
  if (!text || !/[=(#]/.test(text)) return text;
  return applyOutsideFences(text, codeProse);
}
