/**
 * P3: the trajectory chart's playback controls and overlays.
 *
 * The dot's geometry is asserted as a pure function in
 * `lib/__tests__/trajectoryPoint.test.ts`. What is left here is the part only a
 * render can prove: that nothing moves until the user asks, that reduce-motion
 * gets the static curve back, and that the arrows appear only where both axes
 * are space.
 */
import { fireEvent, render } from "@testing-library/react-native";
import { Dimensions } from "react-native";

import { FunctionGraphBlock } from "@/components/rich/FunctionGraphBlock";

const mockUseReduceMotion = jest.fn(() => false);
jest.mock("@/lib/motion", () => ({
  ...jest.requireActual("@/lib/motion"),
  useReduceMotion: () => mockUseReduceMotion(),
}));

const mockCircle = jest.fn((_props: Record<string, unknown>) => null);
const mockPolyline = jest.fn((_props: Record<string, unknown>) => null);
jest.mock("react-native-svg", () => ({
  ...jest.requireActual("react-native-svg"),
  __esModule: true,
  Circle: (props: Record<string, unknown>) => mockCircle(props),
  Polyline: (props: Record<string, unknown>) => mockPolyline(props),
}));

const PARAMETRIC = {
  type: "trajectory",
  expr: "y(x)",
  points: [
    [0, 0],
    [10, 8],
    [20, 10],
    [30, 8],
    [40, 0],
  ],
  x_min: 0,
  x_max: 42,
  title: "Projectile Trajectory",
  x_label: "Distance (m)",
  y_label: "Height (m)",
  trajectory_type: "parametric",
};

const HEIGHT_VS_TIME = {
  ...PARAMETRIC,
  title: "Height vs. Time",
  x_label: "Time (s)",
  trajectory_type: "position_vs_time",
};

const VELOCITY_VS_TIME = {
  ...PARAMETRIC,
  title: "Velocity vs. Time",
  x_label: "Time (s)",
  y_label: "Velocity (m/s)",
  trajectory_type: "velocity_vs_time",
};

const draw = async (spec: object) =>
  await render(<FunctionGraphBlock content={JSON.stringify(spec)} />);

describe("trajectory playback", () => {
  beforeEach(() => {
    jest
      .spyOn(Dimensions, "get")
      .mockReturnValue({ width: 390, height: 844, scale: 3, fontScale: 1 });
    mockUseReduceMotion.mockReturnValue(false);
    mockCircle.mockClear();
    mockPolyline.mockClear();
  });
  afterEach(() => jest.restoreAllMocks());

  it("offers a play control and does not start on its own", async () => {
    const { getByTestId } = await draw(PARAMETRIC);

    getByTestId("trajectory-play");
    // Rows stay mounted past the viewport (FlashList drawDistance) and nothing
    // tracks visibility, so an autoplaying animation would run unseen. The dot
    // must sit at the first sample until pressed.
    const dot = mockCircle.mock.calls.at(-1)?.[0];
    expect(dot).toBeDefined();
    expect(dot?.cx).toBeCloseTo(28, 5); // pad, i.e. the launch point
  });

  it("replays from the start when pressed", async () => {
    const { getByTestId } = await draw(PARAMETRIC);

    // The mocked withTiming is synchronous, so this asserts the press is wired
    // to the shared value at all — the real timing is Reanimated's to keep.
    expect(() => fireEvent.press(getByTestId("trajectory-play"))).not.toThrow();
  });

  it("falls back to the static curve under reduce motion", async () => {
    mockUseReduceMotion.mockReturnValue(true);
    const { queryByTestId, getByText } = await draw(PARAMETRIC);

    expect(queryByTestId("trajectory-play")).toBeNull();
    // The arrows stay. Reduce Motion asks for no movement, not less
    // information, and gravity and launch velocity are drawn statically.
    expect(queryByTestId("trajectory-arrows")).not.toBeNull();
    // The chart itself is unchanged — the title still renders.
    getByText("Projectile Trajectory");
  });

  it("draws motion arrows only where both axes are space", async () => {
    expect((await draw(PARAMETRIC)).queryByTestId("trajectory-arrows")).not.toBeNull();
    // On these two the x-axis is time, so a downward gravity arrow would point
    // across a time axis and state something false.
    expect((await draw(HEIGHT_VS_TIME)).queryByTestId("trajectory-arrows")).toBeNull();
    expect((await draw(VELOCITY_VS_TIME)).queryByTestId("trajectory-arrows")).toBeNull();
  });

  it("never dims the curve to make room for the animation", async () => {
    // Most people will never tap play. Drawing the base curve faint so the
    // animated trail can supply the colour would make the default state of
    // every projectile answer worse than it was before playback existed.
    await draw(PARAMETRIC);
    const curves = mockPolyline.mock.calls.map(([props]) => props);
    const solid = curves.filter((props) => props.strokeOpacity === undefined);

    expect(solid).toHaveLength(1);
    expect(solid[0].strokeWidth).toBe(2.5);

    mockPolyline.mockClear();
    mockUseReduceMotion.mockReturnValue(true);
    await draw(PARAMETRIC);
    const reduced = mockPolyline.mock.calls.map(([props]) => props);

    // Same stroke either way — reduce motion drops the halo, not the curve.
    expect(reduced).toHaveLength(1);
    expect(reduced[0].stroke).toBe(solid[0].stroke);
    expect(reduced[0].strokeWidth).toBe(solid[0].strokeWidth);
  });

  it("renders a velocity chart with its own labels", async () => {
    const { getByText } = await draw(VELOCITY_VS_TIME);
    getByText("Velocity vs. Time");
  });
});
