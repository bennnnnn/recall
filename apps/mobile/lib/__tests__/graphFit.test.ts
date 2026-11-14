import { interactiveFunctionBounds } from "@/lib/math/graphFit";
import { type GraphSpec } from "@/lib/math/graphSpec";
import { type GraphView } from "@/lib/math/graphViewport";

/** A phone card's plot: 336 × 220 less the axis pad. */
const CARD_ASPECT = (336 - 32) / (220 - 32);

/** The server's samples: 96 points across −10…10, rounded to four places. */
function samples(f: (x: number) => number): [number, number][] {
  return Array.from({ length: 96 }, (_, i) => {
    const x = Number((-10 + (20 * i) / 95).toFixed(4));
    return [x, Number(f(x).toFixed(4))] as [number, number];
  }).filter(([, y]) => Number.isFinite(y));
}

function fn(expr: string, f: (x: number) => number, extra: Partial<GraphSpec> = {}): GraphSpec {
  return { type: "function", expr, points: samples(f), x_min: -10, x_max: 10, ...extra } as GraphSpec;
}

function shows(view: GraphView, [x, y]: [number, number]): boolean {
  return x > view.xMin && x < view.xMax && y > view.yMin && y < view.yMax;
}

describe("the window a graph card opens on", () => {
  it.each([
    ["the vertex and roots of y = x² − 4", fn("x^2 - 4", (x) => x * x - 4), [[0, -4], [-2, 0], [2, 0]]],
    ["the cap of y = −x² + 6", fn("6 - x^2", (x) => 6 - x * x), [[0, 6]]],
    ["both intercepts of y = 2x + 5", fn("2x + 5", (x) => 2 * x + 5), [[0, 5], [-2.5, 0]]],
    ["the line y = 7", fn("7", () => 7), [[0, 7]]],
    ["the vertex of y = (x − 8)²", fn("(x - 8)^2", (x) => (x - 8) ** 2), [[8, 0]]],
    ["the turning points of y = x³ − 100x", fn("x^3 - 100x", (x) => x ** 3 - 100 * x), [[5.77, -384.9], [-5.77, 384.9]]],
    ["the peaks of y = 5 sin x", fn("5sin(x)", (x) => 5 * Math.sin(x)), [[Math.PI / 2, 5], [-Math.PI / 2, -5]]],
    ["both crossings of y = x² and y = 2x + 8", fn("x^2", (x) => x * x, {
      expr2: "2x + 8",
      points2: samples((x) => 2 * x + 8),
    }), [[-2, 4], [4, 16]]],
  ] as const)("shows %s", (_name, spec, features) => {
    const view = interactiveFunctionBounds(spec, CARD_ASPECT);
    for (const point of features) expect(shows(view, point as [number, number])).toBe(true);
  });

  it("does not shrink y = (x − 8)² to a needle for its far y-intercept", () => {
    const view = interactiveFunctionBounds(fn("(x - 8)^2", (x) => (x - 8) ** 2), CARD_ASPECT);
    expect(view.yMax - view.yMin).toBeLessThan(20);
  });

  it("shows a vertical line or a point drawn off to one side", () => {
    const line = interactiveFunctionBounds(
      { type: "vertical", expr: "x = 8", x: 8, points: [[8, -10], [8, 10]], y_min: -10, y_max: 10 },
      CARD_ASPECT,
    );
    expect(line.xMax).toBeGreaterThan(8.5);
    const point = interactiveFunctionBounds(
      { type: "function", expr: "(8, 3)", points: [[8, 3]], x_min: 3, x_max: 13 },
      CARD_ASPECT,
    );
    expect(shows(point, [8, 3])).toBe(true);
  });

  it("draws the whole of a circle, still round", () => {
    const loop = Array.from({ length: 97 }, (_, i) => {
      const t = (2 * Math.PI * i) / 96;
      return [Number((5 * Math.cos(t)).toFixed(4)), Number((5 * Math.sin(t)).toFixed(4))] as [number, number];
    });
    const view = interactiveFunctionBounds(
      { type: "function", expr: "x**2 + y**2 = 25", points: loop, x_min: -6, x_max: 6, y_min: -6, y_max: 6 },
      CARD_ASPECT,
    );
    for (const point of [[5, 0], [-5, 0], [0, 5], [0, -5]] as const) {
      expect(shows(view, point as unknown as [number, number])).toBe(true);
    }
    expect((view.xMax - view.xMin) / (view.yMax - view.yMin)).toBeCloseTo(CARD_ASPECT, 6);
  });

  it.each([
    ["y = x²", fn("x^2", (x) => x * x)],
    ["y = tan x", fn("tan(x)", Math.tan)],
    ["y = eˣ, whose tail rounds to 0", fn("e^x", Math.exp)],
    // The server left this pole joined; the card's own samples split it.
    ["y = 1/(x − 2) + 3", fn("3 + 1/(x - 2)", (x) => 3 + 1 / (x - 2))],
  ] as const)("keeps the school window for %s", (_name, spec) => {
    const view = interactiveFunctionBounds(spec, CARD_ASPECT);
    expect(view.xMin).toBe(-6);
    expect(view.xMax).toBe(6);
    expect(view.yMax).toBeCloseTo(6 / CARD_ASPECT, 9);
  });

  it("focuses y = x² − 4x + 3 on its roots, vertex and y-intercept, not the half-empty ±6 window", () => {
    // 2026-11-06: the card ran from −6 to 6 and half the plot was empty.
    const view = interactiveFunctionBounds(fn("x^2 - 4x + 3", (x) => x * x - 4 * x + 3), CARD_ASPECT);
    for (const point of [[1, 0], [3, 0], [2, -1], [0, 3]] as const) {
      expect(shows(view, point as unknown as [number, number])).toBe(true);
    }
    expect(view.xMax - view.xMin).toBeLessThan(8);
    expect(view.xMin).toBeGreaterThan(-3);
    expect(view.xMax).toBeLessThan(6);
    // The arms climb out of the top, not off into a window of empty grid.
    expect(view.yMax).toBeLessThan(10);
  });

  it("shows every point the fence marks", () => {
    const view = interactiveFunctionBounds(
      fn("x^2 - 4x + 3", (x) => x * x - 4 * x + 3, {
        marks: [{ x: 1, y: 0, curve: 1 }, { x: 3, y: 0, curve: 1 }, { x: 2, y: -1, curve: 1 }, { x: 0, y: 3, curve: 1 }],
      }),
      CARD_ASPECT,
    );
    for (const point of [[1, 0], [3, 0], [2, -1], [0, 3]] as const) {
      expect(shows(view, point as unknown as [number, number])).toBe(true);
    }
  });
});


describe("the window the full-screen explorer opens on", () => {
  /** A Galaxy S23's explorer plot, 344 × 480, and a taller one with no editor rows. */
  const EXPLORER_ASPECTS = [(344 - 32) / (480 - 32), (344 - 32) / (640 - 32)];
  const span = (view: GraphView) => [view.xMax - view.xMin, view.yMax - view.yMin];

  it.each(EXPLORER_ASPECTS)("opens y = x² − 4x + 3 on the card's region, filling a plot of aspect %p", (aspect) => {
    // 2026-11-10: the card showed x from −1 to 4, the explorer a thin spike in ±50.
    const spec = fn("x^2 - 4x + 3", (x) => x * x - 4 * x + 3);
    const view = interactiveFunctionBounds(spec, aspect);
    expect(view.xMin).toBeLessThanOrEqual(-1);
    expect(view.xMax).toBeGreaterThanOrEqual(4);
    expect(view.yMin).toBeLessThanOrEqual(-1);
    expect(view.yMax).toBeGreaterThanOrEqual(6);
    const [cardX] = span(interactiveFunctionBounds(spec, CARD_ASPECT));
    const [x, y] = span(view);
    expect(x).toBeLessThan(cardX * 1.5);
    // Taller than wide on a tall plot, but never a column of empty grid.
    expect(y).toBeLessThan(x / aspect + 1e-9);
  });

  it.each([
    ["the steep y = x³ − 100x", fn("x^3 - 100x", (x) => x ** 3 - 100 * x), [[5.77, -384.9], [-5.77, 384.9]]],
    ["the flat y = 0.1x + 2", fn("0.1x + 2", (x) => 0.1 * x + 2), [[0, 2]]],
  ] as const)("shows what the card shows of %s, no wider", (_name, spec, features) => {
    const card = interactiveFunctionBounds(spec, CARD_ASPECT);
    for (const aspect of EXPLORER_ASPECTS) {
      const view = interactiveFunctionBounds(spec, aspect);
      for (const point of features) expect(shows(view, point as [number, number])).toBe(true);
      expect(view.xMin).toBeLessThanOrEqual(card.xMin);
      expect(view.xMax).toBeGreaterThanOrEqual(card.xMax);
      expect(span(view)[0]).toBeLessThan(span(card)[0] * 1.5);
    }
  });

  it("shows a vertical line off to one side, no wider than the card", () => {
    const line = { type: "vertical", expr: "x = 8", x: 8, points: [[8, -10], [8, 10]], y_min: -10, y_max: 10 } as GraphSpec;
    const card = interactiveFunctionBounds(line, CARD_ASPECT);
    for (const aspect of EXPLORER_ASPECTS) {
      const view = interactiveFunctionBounds(line, aspect);
      expect(view.xMax).toBeGreaterThan(8.5);
      expect(span(view)[0]).toBeLessThan(span(card)[0] * 1.5);
    }
  });
});


/** The server's samples across a range the learner named. */
function over(xMin: number, xMax: number, f: (x: number) => number): [number, number][] {
  return Array.from({ length: 96 }, (_, i) => {
    const x = xMin + ((xMax - xMin) * i) / 95;
    return [x, f(x)] as [number, number];
  });
}

describe("a graph over the range the learner named", () => {
  it.each([
    ["a reservoir's depth over weeks 0 to 12", "144 - 4x", 0, 12, (x: number) => 144 - 4 * x],
    ["y = 2x + 1 for x from −3 to 3", "2x + 1", -3, 3, (x: number) => 2 * x + 1],
    ["a conversion graph to 12 inches", "2.54x", 0, 12, (x: number) => 2.54 * x],
    ["a taxi fare over 0 to 10 km", "20 + 8x", 0, 10, (x: number) => 20 + 8 * x],
  ])("shows the whole of %s", (_name, expr, xMin, xMax, f) => {
    const spec = { type: "function", expr, points: over(xMin, xMax, f), x_min: xMin, x_max: xMax, domain_explicit: true } as GraphSpec;
    const view = interactiveFunctionBounds(spec, CARD_ASPECT);
    expect(view.xMin).toBe(xMin);
    expect(view.xMax).toBe(xMax);
    for (const [, y] of spec.points) {
      expect(y).toBeGreaterThanOrEqual(view.yMin);
      expect(y).toBeLessThanOrEqual(view.yMax);
    }
  });

  it("keeps the crop for a curve with a pole across the range", () => {
    const points = over(-Math.PI, Math.PI, Math.tan).filter(([, y]) => Number.isFinite(y));
    const spec = { type: "function", expr: "tan(x)", points, x_min: -Math.PI, x_max: Math.PI, domain_explicit: true } as GraphSpec;
    const view = interactiveFunctionBounds(spec, CARD_ASPECT);
    expect(view.yMax - view.yMin).toBeLessThan(1000);
  });
});
