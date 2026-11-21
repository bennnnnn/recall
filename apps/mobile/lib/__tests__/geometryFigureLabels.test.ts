import fixture from "../../../../docs/fixtures/server_figures.json";

import {
  LABEL_ASCENT,
  LABEL_CHAR,
  LABEL_DESCENT,
  labelStart,
  labelTouches,
  strokesOf,
  type Stroke,
} from "@/lib/math/figurePlacement";
import { figureLayout, parseFigure } from "@/lib/math/geometryFigure";

type Case = { id: string; figure: Record<string, unknown> };

/** Card widths from the smallest phone's (screen less 48) to a tablet's, every 8px. */
const WIDTHS = Array.from({ length: 38 }, (_, i) => 272 + i * 8);

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
    const start = labelStart(label);
    const off =
      start < 0 ||
      start + label.text.length * LABEL_CHAR > layout.width ||
      label.y - LABEL_ASCENT < 0 ||
      label.y + LABEL_DESCENT > layout.height;
    return [
      ...(count
        ? [`"${label.text}" touches ${count} line(s) or label(s)`]
        : []),
      ...(off ? [`"${label.text}" runs off the card`] : []),
    ];
  });
}

describe("the server's figures for the geometry corpus", () => {
  const cases = (fixture as { cases: Case[] }).cases;

  it.each(
    cases.flatMap((c) => WIDTHS.map((w) => [c.id, w, c.figure] as const)),
  )(
    "%s at %ipx writes no label over a line, another label or the card's edge",
    (_id, width, figure) => {
      expect(clashes(figure, width)).toEqual([]);
    },
  );
});

describe("an angle the figure names", () => {
  it("keeps its name when it is a right angle too (review, #2518)", () => {
    const named = (fixture as { cases: Case[] }).cases.filter((c) =>
      (
        (c.figure.angles as
          { label?: string; right?: boolean }[] | undefined) ?? []
      ).some((a) => a.right && a.label),
    );
    expect(named.length).toBeGreaterThan(0);
    for (const c of named) {
      const spec = parseFigure(c.figure);
      expect(spec).not.toBeNull();
      const texts = figureLayout(spec!, 320).labels.map((label) => label.text);
      for (const angle of (
        c.figure.angles as { label?: string; right?: boolean }[]
      ).filter((a) => a.right && a.label)) {
        expect(texts).toContain(angle.label);
      }
    }
  });
});
