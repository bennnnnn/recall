/**
 * A still scene the server built in stages, as `SimulationBlock` draws it: the
 * arrows grow in the server's order, it plays once by itself with the moving
 * scenes' replay control, and Reduce Motion gets the finished diagram. A scene
 * with no stages draws as it did (its picture is pinned by
 * `SimulationBlockSnapshot.test.tsx`). The clock itself is asserted as plain
 * functions in `lib/__tests__/simulationStages.test.ts`.
 *
 * Skia's paths are recorded, so a test can see how much of an arrow is drawn.
 */
import { fireEvent, render } from "@testing-library/react-native";
import { Group, Path } from "@shopify/react-native-skia";

import { SimulationBlock } from "@/components/rich/SimulationBlock";
import { StatedVector } from "@/components/rich/simulation/vectors";
import { RESOLVED } from "@/lib/__tests__/fixtures/stagedScenes";

const HIDDEN = { includeHiddenElements: true };

const mockUseReduceMotion = jest.fn<boolean | null, []>(() => false);
jest.mock("@/lib/motion", () => ({
  ...jest.requireActual("@/lib/motion"),
  useReduceMotion: () => mockUseReduceMotion() ?? false,
  useReduceMotionSetting: () => mockUseReduceMotion(),
}));

/** When set, the scene's clock is held at this moment instead of running. */
let mockHeldProgress: number | null = null;
jest.mock("@/components/rich/usePlayback", () => {
  const actual = jest.requireActual("@/components/rich/usePlayback");
  return {
    ...actual,
    usePlayback: (options: unknown) => {
      const playback = actual.usePlayback(options);
      return mockHeldProgress === null
        ? playback
        : { ...playback, progress: { value: mockHeldProgress } };
    },
  };
});

jest.mock("@shopify/react-native-skia", () => {
  const actual = jest.requireActual("@shopify/react-native-skia");
  const named = (name: string) => {
    const Primitive = () => null;
    Primitive.displayName = name;
    return Primitive;
  };
  const makePath = () => {
    const ops: (string | number)[][] = [];
    const path = {
      ops,
      moveTo: (x: number, y: number) => ops.push(["M", x, y]) && path,
      lineTo: (x: number, y: number) => ops.push(["L", x, y]) && path,
      close: () => ops.push(["Z"]) && path,
      detach: () => path,
    };
    return path;
  };
  return {
    ...actual,
    Path: named("Path"),
    Circle: named("Circle"),
    DashPathEffect: named("DashPathEffect"),
    Group: ({ children }: { children?: unknown }) => children ?? null,
    Skia: { ...actual.Skia, Path: { Make: makePath }, PathBuilder: { Make: makePath } },
  };
});

type Ops = (string | number)[][];

type Fiber = {
  type: unknown;
  memoizedProps: Record<string, unknown>;
  child: Fiber | null;
  sibling: Fiber | null;
  return: Fiber | null;
};

type View = Awaited<ReturnType<typeof render>>;

/** The staged arrow's component, which `sceneArrows.tsx` keeps to itself: found by its name. */
const STAGED_VECTOR = "StagedVector";

function isType(node: Fiber, type: unknown): boolean {
  if (typeof type === "string") return (node.type as { name?: string } | null)?.name === type;
  return node.type === type;
}

/** Every fiber under `fiber` (itself included) of this component type, in render order. */
function fibersUnder(fiber: Fiber | null, type: unknown, out: Fiber[] = []): Fiber[] {
  for (let node = fiber; node; node = node.sibling) {
    if (isType(node, type)) out.push(node);
    fibersUnder(node.child, type, out);
  }
  return out;
}

/** Every element of this component type in the rendered tree. */
function allOfType(view: View, type: unknown): Fiber[] {
  let top = view.root?.unstable_fiber as Fiber | null | undefined;
  while (top?.return) top = top.return;
  return fibersUnder(top ?? null, type);
}

/** How much of a staged arrow is drawn: the reach of its first path. */
function drawnOf(arrow: Fiber): number {
  return reach(fibersUnder(arrow.child, Path)[0].memoizedProps.path);
}

/** Every staged Group's opacity this frame. */
function opacities(view: View): number[] {
  return allOfType(view, Group)
    .map((group) => (group.memoizedProps.opacity as { value: number } | undefined)?.value)
    .filter((opacity): opacity is number => typeof opacity === "number");
}

/** How far a path reaches from where it starts: an arrow's drawn length, head included. */
function reach(path: unknown): number {
  const ops = ((path as { value?: { ops: Ops } }).value ?? (path as { ops: Ops })).ops;
  const points = ops.filter((op) => op.length === 3) as [string, number, number][];
  if (points.length === 0) return 0;
  const [, x0, y0] = points[0];
  return Math.max(...points.map(([, x, y]) => Math.hypot(x - x0, y - y0)));
}

const STAGED = JSON.stringify(RESOLVED);
const UNSTAGED = JSON.stringify({
  ...RESOLVED,
  vectors: RESOLVED.vectors.map(({ stage: _stage, ...vector }) => vector),
  angles: RESOLVED.angles.map(({ stage: _stage, ...angle }) => angle),
});

/** Each staged arrow's turn and how much of it is drawn. */
async function arrowsAt(progress: number | null) {
  mockHeldProgress = progress;
  const view = await render(<SimulationBlock content={STAGED} />);
  return allOfType(view, STAGED_VECTOR).map((arrow) => ({
    turn: arrow.memoizedProps.turn as number,
    drawn: drawnOf(arrow),
  }));
}

/** Every staged Group's opacity this frame: the labels and arcs waiting for their arrows. */
async function revealsAt(progress: number) {
  mockHeldProgress = progress;
  const view = await render(<SimulationBlock content={STAGED} />);
  return opacities(view);
}

beforeEach(() => {
  mockHeldProgress = null;
  mockUseReduceMotion.mockReturnValue(false);
});

describe("SimulationBlock: a scene built in stages", () => {
  it("draws the arrows in the server's order: a later one waits while an earlier one grows", async () => {
    const whole = await arrowsAt(1);
    expect(whole.map((arrow) => arrow.turn)).toEqual([0, 1, 2]);
    expect(whole.every((arrow) => arrow.drawn > 0)).toBe(true);

    // A tenth of the way in: the given vector is growing, its components are not begun.
    const early = await arrowsAt(0.1);
    expect(early[0].drawn).toBeGreaterThan(0);
    expect(early[0].drawn).toBeLessThan(whole[0].drawn);
    expect(early[1].drawn).toBe(0);
    expect(early[2].drawn).toBe(0);

    // Past half way: the vector and its horizontal component are whole, the vertical one not begun.
    const middle = await arrowsAt(0.6);
    expect(middle[0].drawn).toBeCloseTo(whole[0].drawn, 5);
    expect(middle[1].drawn).toBeCloseTo(whole[1].drawn, 5);
    expect(middle[2].drawn).toBe(0);
  });

  it("holds back the labels and the angle arc until their arrows are drawn", async () => {
    expect((await revealsAt(0)).every((opacity) => opacity === 0)).toBe(true);
    const done = await revealsAt(1);
    // Three vector labels, the arc and its label.
    expect(done).toHaveLength(5);
    expect(done.every((opacity) => opacity === 1)).toBe(true);
  });

  it("shows the given angle with the given vector, before either component", async () => {
    // A third of the way in: stage 0 is whole and shown, stages 1 and 2 not begun.
    // In draw order: the arc, its label, then the three vector labels.
    expect(await revealsAt(0.34)).toEqual([1, 1, 1, 0, 0]);
  });

  it("plays once by itself and offers the moving scenes' play and pause", async () => {
    const { getByTestId, getByLabelText } = await render(<SimulationBlock content={STAGED} />);

    expect(getByTestId("simulation-stages-3", HIDDEN)).toBeTruthy();
    expect(getByTestId("simulation-stop-symbol").props.name).toBe("pause");
    await fireEvent.press(getByLabelText("rich.simulation_pause_a11y"));
    expect(getByTestId("simulation-play-symbol").props.name).toBe("play");
  });

  it("shows the finished diagram under Reduce Motion, with Play to build it", async () => {
    mockUseReduceMotion.mockReturnValue(true);
    const view = await render(<SimulationBlock content={STAGED} />);
    // The test's derived values are read once a render, so render again to see where the clock rests.
    await view.rerender(<SimulationBlock content={STAGED} />);
    const arrows = allOfType(view, STAGED_VECTOR);
    expect(arrows).toHaveLength(3);
    expect(arrows.every((arrow) => drawnOf(arrow) > 0)).toBe(true);
    expect(view.getByTestId("simulation-static", HIDDEN)).toBeTruthy();
    expect(view.getByTestId("simulation-play-symbol").props.name).toBe("play");
    const shown = opacities(view);
    expect(shown).toHaveLength(5);
    expect(shown.every((opacity) => opacity === 1)).toBe(true);
  });

  it("tells a screen reader what it told it before", async () => {
    const staged = await render(<SimulationBlock content={STAGED} />);
    const label = staged.getByRole("image").props.accessibilityLabel;
    const plain = await render(<SimulationBlock content={UNSTAGED} />);
    expect(plain.getByRole("image").props.accessibilityLabel).toBe(label);
    expect(label).toContain("10 N");
  });

  it("draws a scene with no stages at once, as before: no growing arrows and no Play", async () => {
    const view = await render(<SimulationBlock content={UNSTAGED} />);

    expect(allOfType(view, STAGED_VECTOR)).toHaveLength(0);
    expect(allOfType(view, StatedVector)).toHaveLength(3);
    expect(opacities(view)).toHaveLength(0);
    expect(view.queryByTestId("simulation-stages-3", HIDDEN)).toBeNull();
    expect(view.queryByTestId("simulation-control")).toBeNull();
  });
});
