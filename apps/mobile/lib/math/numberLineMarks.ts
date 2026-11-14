/**
 * The numbers a number line shows, labelled as the question writes them ("−5/2", "1.5"),
 * above their dots. Two labels that would touch sit on two rows.
 */
type NumberLineMarkLabel = { text: string; px: number; row: 0 | 1 };

/** An estimate of a label's width per character at the tick font size. */
const CHAR_WIDTH = 6.5;
const GAP = 4;

export function numberLineMarkLabels(
  marks: { x: number; label?: string }[] | undefined,
  toPx: (value: number) => number,
): NumberLineMarkLabel[] {
  const labelled = (marks ?? [])
    .filter((mark): mark is { x: number; label: string } => !!mark.label)
    .map((mark) => ({ text: mark.label, px: toPx(mark.x) }))
    .sort((a, b) => a.px - b.px);
  const ends: [number, number] = [-Infinity, -Infinity];
  return labelled.map(({ text, px }) => {
    const half = (text.length * CHAR_WIDTH) / 2;
    const row: 0 | 1 = px - half >= ends[0] + GAP ? 0 : px - half >= ends[1] + GAP ? 1 : ends[0] <= ends[1] ? 0 : 1;
    ends[row] = px + half;
    return { text, px, row };
  });
}

/** How far above the line a label row's baseline sits. */
export function markLabelRise(row: 0 | 1): number {
  return 12 + row * 14;
}
