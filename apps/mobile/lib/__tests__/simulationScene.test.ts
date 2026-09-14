/**
 * P14: parsing and geometry for the `simulation` fence.
 *
 * The scene's arithmetic is asserted here as plain functions; what only a
 * render can prove — that nothing autoplays, that Reduce Motion still draws
 * something — is in `components/__tests__/SimulationBlock.test.tsx`.
 *
 * The property this file exists for is the uniform scale. A graph stretches
 * each axis to fill its box, and doing that here would turn an orbit into an
 * ellipse and a 30° launch into some other angle — a picture that contradicts
 * the verified number printed beside it.
 */
import {
  arrowPolyline,
  parseSimulationSpec,
  projectPath,
  simulationTransform,
  tangentAt,
  worldToScreen,
} from "@/lib/math/simulation";

const PROJECTILE = {
  type: "projectile_motion",
  title: "Projectile",
  bodies: [
    {
      radius: 0.5,
      role: "primary",
      path: [
        [0, 0],
        [10, 7],
        [20, 10],
        [30, 7],
        [40, 0],
      ],
    },
  ],
  x_min: 0,
  x_max: 40,
  y_min: 0,
  y_max: 20,
  arrows: ["velocity", "gravity"],
  ground: true,
};

const ORBIT = {
  type: "orbit",
  bodies: [
    {
      radius: 0.4,
      role: "primary",
      path: [
        [5, 0],
        [0, 5],
        [-5, 0],
        [0, -5],
        [5, 0],
      ],
    },
  ],
  x_min: -6,
  x_max: 6,
  y_min: -6,
  y_max: 6,
  arrows: ["velocity", "centripetal"],
  centre: [0, 0],
  ground: false,
};

function parse(spec: object) {
  return parseSimulationSpec(JSON.stringify(spec));
}

describe("parseSimulationSpec", () => {
  it("reads a projectile scene", () => {
    const spec = parse(PROJECTILE);

    expect(spec).not.toBeNull();
    expect(spec!.type).toBe("projectile_motion");
    expect(spec!.bodies).toHaveLength(1);
    expect(spec!.bodies[0].path).toHaveLength(5);
    expect(spec!.arrows).toEqual(["velocity", "gravity"]);
    expect(spec!.ground).toBe(true);
  });

  it("reads an orbit scene with its centre", () => {
    const spec = parse(ORBIT);

    expect(spec!.type).toBe("orbit");
    expect(spec!.centre).toEqual({ x: 0, y: 0 });
    expect(spec!.arrows).toContain("centripetal");
  });

  it("drops a centripetal arrow that has no centre to point at", () => {
    // "Toward the centre" with no centre would be drawn toward the origin of
    // the scene box, which is a different place and a wrong picture.
    const spec = parse({ ...ORBIT, centre: undefined });

    expect(spec!.arrows).toEqual(["velocity"]);
  });

  it.each([
    ["an unknown type", { ...PROJECTILE, type: "explosion" }],
    ["no bodies", { ...PROJECTILE, bodies: [] }],
    ["a one-sample path", { ...PROJECTILE, bodies: [{ ...PROJECTILE.bodies[0], path: [[0, 0]] }] }],
    ["a non-finite sample", {
      ...PROJECTILE,
      bodies: [{ ...PROJECTILE.bodies[0], path: [[0, 0], [1, null]] }],
    }],
    ["inverted bounds", { ...PROJECTILE, x_min: 40, x_max: 0 }],
  ])("refuses %s", (_label, bad) => {
    expect(parse(bad)).toBeNull();
  });

  it("refuses bodies sampled at different rates", () => {
    // One clock walks every body, so mismatched lengths would show a two-body
    // scene out of step — a collision at the wrong moment.
    const spec = parse({
      ...PROJECTILE,
      bodies: [
        PROJECTILE.bodies[0],
        { ...PROJECTILE.bodies[0], path: [[0, 0], [1, 1], [2, 2]] },
      ],
    });

    expect(spec).toBeNull();
  });

  it("refuses text that is not JSON", () => {
    expect(parseSimulationSpec("not json at all")).toBeNull();
  });
});

describe("simulationTransform", () => {
  it("uses one scale for both axes", () => {
    // The whole reason this is not `mapGraphPoint`. A 12x12 world in a
    // 360x240 box is limited by height, so both axes take the height's scale.
    const spec = parse(ORBIT)!;
    const t = simulationTransform(spec, 360, 240, 24);

    const right = worldToScreen(5, 0, t);
    const top = worldToScreen(0, 5, t);
    const centre = worldToScreen(0, 0, t);

    expect(right.px - centre.px).toBeCloseTo(centre.py - top.py, 6);
  });

  it("keeps a circular path circular", () => {
    const spec = parse(ORBIT)!;
    const t = simulationTransform(spec, 360, 240, 24);
    const centre = worldToScreen(0, 0, t);

    const radii = projectPath(spec.bodies[0].path, t).map((p) =>
      Math.hypot(p.px - centre.px, p.py - centre.py),
    );

    for (const r of radii) expect(r).toBeCloseTo(radii[0], 6);
  });

  it("centres the scene in whichever direction has slack", () => {
    const spec = parse(ORBIT)!;
    const t = simulationTransform(spec, 360, 240, 24);
    const left = worldToScreen(-6, 0, t);
    const right = worldToScreen(6, 0, t);

    expect((left.px + right.px) / 2).toBeCloseTo(180, 6);
  });

  it("puts world y upward and screen y downward", () => {
    const spec = parse(PROJECTILE)!;
    const t = simulationTransform(spec, 360, 240, 24);

    expect(worldToScreen(0, 10, t).py).toBeLessThan(worldToScreen(0, 0, t).py);
  });
});

describe("tangentAt", () => {
  it("points along the direction of travel", () => {
    const spec = parse(PROJECTILE)!;
    const t = simulationTransform(spec, 360, 240, 24);
    const track = projectPath(spec.bodies[0].path, t);

    // Rising at launch: x increases, and screen y decreases going up.
    const start = tangentAt(track, 0);
    expect(start.dx).toBeGreaterThan(0);
    expect(start.dy).toBeLessThan(0);

    // Falling at the end: still moving right, now moving down the screen.
    const end = tangentAt(track, 1);
    expect(end.dx).toBeGreaterThan(0);
    expect(end.dy).toBeGreaterThan(0);
  });

  it("never returns a zero-length direction", () => {
    // Adjacent samples on a dense path can round to the same pixel, and a
    // zero-length tangent makes the velocity arrow flip about at random.
    const flat = [
      { px: 10, py: 10 },
      { px: 10, py: 10 },
      { px: 10, py: 10 },
    ];

    const { dx, dy } = tangentAt(flat, 0.5);
    expect(Math.hypot(dx, dy)).toBeGreaterThan(0);
  });

  it("clamps progress outside 0..1", () => {
    const spec = parse(PROJECTILE)!;
    const t = simulationTransform(spec, 360, 240, 24);
    const track = projectPath(spec.bodies[0].path, t);

    expect(tangentAt(track, -3)).toEqual(tangentAt(track, 0));
    expect(tangentAt(track, 9)).toEqual(tangentAt(track, 1));
  });
});

describe("arrowPolyline", () => {
  it("draws shaft and both barbs as one five-point path", () => {
    const points = arrowPolyline({ px: 0, py: 0 }, 1, 0, 40, 8)
      .split(" ")
      .map((pair) => pair.split(",").map(Number));

    expect(points).toHaveLength(5);
    // tail, tip, barb, back to tip, other barb
    expect(points[0]).toEqual([0, 0]);
    expect(points[1]).toEqual([40, 0]);
    expect(points[3]).toEqual([40, 0]);
    // The barbs sit behind the tip and on opposite sides of the shaft.
    expect(points[2][0]).toBeLessThan(40);
    expect(points[4][0]).toBeLessThan(40);
    expect(Math.sign(points[2][1])).toBe(-Math.sign(points[4][1]));
  });

  it("has the requested length whichever way it points", () => {
    // Coordinates are emitted at 2 dp, so the tolerance is set by the string
    // format rather than the geometry; anything tighter tests toFixed.
    for (const [dx, dy] of [
      [1, 0],
      [0, 1],
      [-3, 4],
      [2, -2],
    ]) {
      const [tip] = arrowPolyline({ px: 100, py: 100 }, dx, dy, 40, 8)
        .split(" ")
        .slice(1, 2)
        .map((pair) => pair.split(",").map(Number));

      expect(Math.hypot(tip[0] - 100, tip[1] - 100)).toBeCloseTo(40, 1);
    }
  });

  it("survives a zero direction rather than emitting NaN", () => {
    expect(arrowPolyline({ px: 5, py: 5 }, 0, 0, 40, 8)).not.toContain("NaN");
  });
});
