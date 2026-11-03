import { act, fireEvent, render } from "@testing-library/react-native";

import { ReadAloudPlayer } from "@/features/speech/components/ReadAloudPlayer";
import {
  endReadAloud,
  pauseReadAloud,
  readAloudChunk,
  readAloudClipEnded,
  readAloudClipTime,
  readAloudPlaying,
  readAloudSession,
  startReadAloud,
} from "@/features/speech/model/readAloudSession";

jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));
jest.mock("@/lib/sentry", () => ({ reportReadAloudControlFailed: jest.fn() }));

const controls = { pause: jest.fn(), resume: jest.fn(), canPause: true };

afterEach(async () => {
  await act(async () => endReadAloud());
  jest.clearAllMocks();
});

it("shows nothing while no reply is read", async () => {
  const view = await render(<ReadAloudPlayer visible bottomOffset={80} />);
  expect(view.queryByTestId("read-aloud-player")).toBeNull();
});

it("says the voice is being prepared, at 0:00, before any sound", async () => {
  const view = await render(<ReadAloudPlayer visible bottomOffset={80} />);
  await act(async () => {
    startReadAloud("m1");
  });
  expect(view.getByLabelText(/^chat.read_aloud_preparing,/)).toBeTruthy();
  // The time, not a title or the reply's words: those are on the screen above it.
  expect(view.getByTestId("read-aloud-player-time")).toHaveTextContent("0:00");
  expect(view.queryByText("chat.read_aloud_preparing")).toBeNull();
  // Nothing plays yet, so nothing to pause: only Stop.
  expect(view.queryByTestId("read-aloud-player-toggle")).toBeNull();
  expect(view.getByTestId("read-aloud-player-stop")).toBeTruthy();
});

it("pauses and resumes what is playing, and shows how far it has got", async () => {
  const view = await render(<ReadAloudPlayer visible bottomOffset={80} />);
  await act(async () => {
    startReadAloud("m1");
    readAloudChunk(1, 2);
    readAloudPlaying(controls, true);
    readAloudClipTime(1, 2);
  });
  expect(view.getByLabelText(/^chat.read_aloud_playing,/)).toBeTruthy();
  expect(readAloudSession.get()?.progress).toBe(0.75);

  await fireEvent.press(view.getByRole("button", { name: "chat.read_aloud_pause" }));
  expect(controls.pause).toHaveBeenCalledTimes(1);
  expect(view.getByLabelText(/^chat.read_aloud_paused,/)).toBeTruthy();

  await fireEvent.press(view.getByRole("button", { name: "chat.read_aloud_resume" }));
  expect(controls.resume).toHaveBeenCalledTimes(1);
  expect(view.getByLabelText(/^chat.read_aloud_playing,/)).toBeTruthy();
});

it("offers Stop alone for a voice that cannot pause (the phone's own, on Android)", async () => {
  const view = await render(<ReadAloudPlayer visible bottomOffset={80} />);
  await act(async () => {
    startReadAloud("m1");
    readAloudPlaying({ ...controls, canPause: false }, false);
  });
  expect(view.queryByTestId("read-aloud-player-toggle")).toBeNull();
  expect(readAloudSession.get()?.progress).toBeNull();
});

it("stops the reading and closes on Stop", async () => {
  const view = await render(<ReadAloudPlayer visible bottomOffset={80} />);
  const stop = jest.fn();
  await act(async () => {
    startReadAloud("m1", stop);
  });
  await fireEvent.press(view.getByRole("button", { name: "chat.read_aloud_stop" }));
  expect(stop).toHaveBeenCalledTimes(1);
  expect(view.queryByTestId("read-aloud-player")).toBeNull();
});

it("keeps a newer reading when the one before it ends", () => {
  const first = startReadAloud("m1");
  startReadAloud("m2");
  endReadAloud(first);
  expect(readAloudSession.get()?.messageId).toBe("m2");
});

it("offers no pause between clips: the clip that ended has no player left", async () => {
  const view = await render(<ReadAloudPlayer visible bottomOffset={80} />);
  await act(async () => {
    startReadAloud("m1");
    readAloudChunk(0, 2);
    readAloudPlaying(controls, true);
    readAloudClipEnded();
  });
  expect(view.getByLabelText(/^chat.read_aloud_preparing,/)).toBeTruthy();
  expect(view.queryByTestId("read-aloud-player-toggle")).toBeNull();
  pauseReadAloud();
  expect(controls.pause).not.toHaveBeenCalled();
});

it("keeps playing, and reports, when a pause fails", async () => {
  const { reportReadAloudControlFailed } = jest.requireMock("@/lib/sentry");
  const failing = { ...controls, pause: jest.fn(() => { throw new Error("released"); }) };
  await act(async () => {
    startReadAloud("m1");
    readAloudPlaying(failing, true);
  });
  expect(() => pauseReadAloud()).not.toThrow();
  expect(readAloudSession.get()?.phase).toBe("playing");
  expect(reportReadAloudControlFailed).toHaveBeenCalledTimes(1);
});

it("shows the time heard, and the whole length once the last clip plays", async () => {
  const view = await render(<ReadAloudPlayer visible bottomOffset={80} />);
  await act(async () => {
    startReadAloud("m1");
    readAloudChunk(0, 2);
    readAloudPlaying(controls, true);
    readAloudClipTime(4.2, 6);
  });
  expect(view.getByTestId("read-aloud-player-time")).toHaveTextContent("0:04");
  await act(async () => {
    readAloudClipEnded();
    readAloudChunk(1, 2);
    readAloudPlaying(controls, true);
    readAloudClipTime(3, 5);
  });
  // 6 s heard in the first clip, 3 s into the last one of 5 s.
  expect(view.getByTestId("read-aloud-player-time")).toHaveTextContent("0:09 / 0:11");
});

it("times the phone's own voice by the clock, and stops the clock on pause", async () => {
  const now = jest.spyOn(Date, "now").mockReturnValue(1_000);
  const view = await render(<ReadAloudPlayer visible bottomOffset={80} />);
  await act(async () => {
    startReadAloud("m1");
    readAloudPlaying(controls, false);
  });
  now.mockReturnValue(8_500);
  await act(async () => {
    pauseReadAloud();
  });
  expect(view.getByTestId("read-aloud-player-time")).toHaveTextContent("0:07");
  now.mockReturnValue(60_000);
  await act(async () => {});
  expect(view.getByTestId("read-aloud-player-time")).toHaveTextContent("0:07");
  now.mockRestore();
});
