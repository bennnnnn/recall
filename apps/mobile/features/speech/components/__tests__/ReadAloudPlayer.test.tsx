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

it("says the voice is being prepared, with the reply it will read, before any sound", async () => {
  const view = await render(<ReadAloudPlayer visible bottomOffset={80} />);
  await act(async () => {
    startReadAloud("m1", "**Rayleigh scattering** makes the sky look blue.");
  });
  expect(view.getByText("chat.read_aloud_preparing")).toBeTruthy();
  expect(view.getByText("Rayleigh scattering makes the sky look blue.")).toBeTruthy();
  // Nothing plays yet, so nothing to pause: only Stop.
  expect(view.queryByTestId("read-aloud-player-toggle")).toBeNull();
  expect(view.getByTestId("read-aloud-player-stop")).toBeTruthy();
});

it("pauses and resumes what is playing, and shows how far it has got", async () => {
  const view = await render(<ReadAloudPlayer visible bottomOffset={80} />);
  await act(async () => {
    startReadAloud("m1", "A reply.");
    readAloudChunk(1, 2);
    readAloudPlaying(controls, true);
    readAloudClipTime(1, 2);
  });
  expect(view.getByText("chat.read_aloud_playing")).toBeTruthy();
  expect(readAloudSession.get()?.progress).toBe(0.75);

  await fireEvent.press(view.getByRole("button", { name: "chat.read_aloud_pause" }));
  expect(controls.pause).toHaveBeenCalledTimes(1);
  expect(view.getByText("chat.read_aloud_paused")).toBeTruthy();

  await fireEvent.press(view.getByRole("button", { name: "chat.read_aloud_resume" }));
  expect(controls.resume).toHaveBeenCalledTimes(1);
  expect(view.getByText("chat.read_aloud_playing")).toBeTruthy();
});

it("offers Stop alone for a voice that cannot pause (the phone's own, on Android)", async () => {
  const view = await render(<ReadAloudPlayer visible bottomOffset={80} />);
  await act(async () => {
    startReadAloud("m1", "A reply.");
    readAloudPlaying({ ...controls, canPause: false }, false);
  });
  expect(view.queryByTestId("read-aloud-player-toggle")).toBeNull();
  expect(readAloudSession.get()?.progress).toBeNull();
});

it("stops the reading and closes on Stop", async () => {
  const view = await render(<ReadAloudPlayer visible bottomOffset={80} />);
  const stop = jest.fn();
  await act(async () => {
    startReadAloud("m1", "A reply.", stop);
  });
  await fireEvent.press(view.getByRole("button", { name: "chat.read_aloud_stop" }));
  expect(stop).toHaveBeenCalledTimes(1);
  expect(view.queryByTestId("read-aloud-player")).toBeNull();
});

it("keeps a newer reading when the one before it ends", () => {
  const first = startReadAloud("m1", "One.");
  startReadAloud("m2", "Two.");
  endReadAloud(first);
  expect(readAloudSession.get()?.messageId).toBe("m2");
});

it("offers no pause between clips: the clip that ended has no player left", async () => {
  const view = await render(<ReadAloudPlayer visible bottomOffset={80} />);
  await act(async () => {
    startReadAloud("m1", "A reply.");
    readAloudChunk(0, 2);
    readAloudPlaying(controls, true);
    readAloudClipEnded();
  });
  expect(view.getByText("chat.read_aloud_preparing")).toBeTruthy();
  expect(view.queryByTestId("read-aloud-player-toggle")).toBeNull();
  pauseReadAloud();
  expect(controls.pause).not.toHaveBeenCalled();
});

it("keeps playing, and reports, when a pause fails", async () => {
  const { reportReadAloudControlFailed } = jest.requireMock("@/lib/sentry");
  const failing = { ...controls, pause: jest.fn(() => { throw new Error("released"); }) };
  await act(async () => {
    startReadAloud("m1", "A reply.");
    readAloudPlaying(failing, true);
  });
  expect(() => pauseReadAloud()).not.toThrow();
  expect(readAloudSession.get()?.phase).toBe("playing");
  expect(reportReadAloudControlFailed).toHaveBeenCalledTimes(1);
});
