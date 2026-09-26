/** Native trajectory playback behavior: autoplay, pause/resume, and reduced motion. */
import { fireEvent, render } from "@testing-library/react-native";
import { Dimensions } from "react-native";

import { FunctionGraphBlock } from "@/components/rich/FunctionGraphBlock";

const mockUseReduceMotion = jest.fn(() => false);
jest.mock("@/lib/motion", () => ({
  ...jest.requireActual("@/lib/motion"),
  useReduceMotion: () => mockUseReduceMotion(),
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

describe("native trajectory playback", () => {
  beforeEach(() => {
    jest
      .spyOn(Dimensions, "get")
      .mockReturnValue({ width: 390, height: 844, scale: 3, fontScale: 1 });
    mockUseReduceMotion.mockReturnValue(false);
  });
  afterEach(() => jest.restoreAllMocks());

  it("renders on Skia and starts automatically with the pause icon", async () => {
    const { getByTestId } = await draw(PARAMETRIC);

    expect(getByTestId("trajectory-canvas")).toBeTruthy();
    expect(getByTestId("trajectory-control")).toBeTruthy();
    expect(getByTestId("trajectory-stop-symbol").props.name).toBe("pause");
  });

  it("pauses and resumes from the triangle play button", async () => {
    const { getByLabelText, getByTestId } = await draw(PARAMETRIC);

    await fireEvent.press(getByLabelText("rich.simulation_pause_a11y"));
    expect(getByTestId("trajectory-play-symbol").props.name).toBe("play");
    await fireEvent.press(getByLabelText("rich.simulation_play_a11y"));
    expect(getByTestId("trajectory-stop-symbol").props.name).toBe("pause");
  });

  it("keeps a complete static chart under Reduce Motion", async () => {
    mockUseReduceMotion.mockReturnValue(true);
    const { getByTestId, getByText, queryByTestId } = await draw(PARAMETRIC);

    expect(getByTestId("trajectory-canvas")).toBeTruthy();
    expect(queryByTestId("trajectory-control")).toBeNull();
    expect(getByTestId("trajectory-arrows")).toBeTruthy();
    getByText("Projectile Trajectory");
  });

  it("draws motion arrows only where both axes are space", async () => {
    expect((await draw(PARAMETRIC)).queryByTestId("trajectory-arrows")).not.toBeNull();
    expect((await draw(HEIGHT_VS_TIME)).queryByTestId("trajectory-arrows")).toBeNull();
    expect((await draw(VELOCITY_VS_TIME)).queryByTestId("trajectory-arrows")).toBeNull();
  });

  it("renders a velocity chart with its own title", async () => {
    const { getByText } = await draw(VELOCITY_VS_TIME);
    getByText("Velocity vs. Time");
  });
});
