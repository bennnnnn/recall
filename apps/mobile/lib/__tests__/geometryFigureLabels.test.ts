import fixture from "../../../../docs/fixtures/server_figures.json";

import { labelTouches, strokesOf, type Stroke } from "@/lib/math/figurePlacement";
import { figureLayout, parseFigure } from "@/lib/math/geometryFigure";

type Case = { id: string; figure: Record<string, unknown> };

/** The card widths of a small phone, an iPhone and a tablet. */
const WIDTHS = [300, 360, 560];

function clashes(raw: Record<string, unknown>, width: number): string[] {
  const spec = parseFigure(raw);
  if (!spec) return ["not read"];
  const layout = figureLayout(spec, width);
  const strokes: Stroke[] = [
    ...layout.lines.map((line): Stroke => [line.from, line.to]),
    ...layout.marks,
    ...layout.arcs.flatMap((arc) => strokesOf(arc.points)),
    ...layout.angleArcs.flatMap(strokesOf),
    ...layout.dots.map((dot): Stroke => [dot, dot]),
  ];
  return layout.labels.flatMap((label, i) => {
    const count = labelTouches(label, strokes, layout.labels.slice(0, i));
    return count ? [`"${label.text}" touches ${count} line(s) or label(s)`] : [];
  });
}

describe("the server's figures for the geometry corpus", () => {
  const cases = (fixture as { cases: Case[] }).cases;

  it.each(cases.flatMap((c) => WIDTHS.map((w) => [c.id, w, c.figure] as const)))(
    "%s at %ipx writes no label over a line or another label",
    (_id, width, figure) => {
      expect(clashes(figure, width)).toEqual([]);
    },
  );
});
