import { requireOptionalNativeModule } from "expo-modules-core";

import { startCallAudio } from "@/features/speech/model/callAudio";

jest.mock("expo-modules-core", () => ({ requireOptionalNativeModule: jest.fn() }));

const nativeModule = requireOptionalNativeModule as jest.Mock;

function callAudioModule() {
  const listeners = new Set<() => void>();
  return {
    startAsync: jest.fn(async (): Promise<void> => undefined),
    stopAsync: jest.fn(async () => undefined),
    addListener: jest.fn((event: string, listener: () => void) => {
      if (event === "onInterrupted") listeners.add(listener);
      return { remove: () => listeners.delete(listener) };
    }),
    /** What the module sends when a phone call or another app takes the audio. */
    interrupt: () => listeners.forEach((listener) => listener()),
  };
}

const flush = () => new Promise<void>((done) => setImmediate(() => done()));

describe("live talk's call route", () => {
  beforeEach(() => {
    nativeModule.mockReset();
    jest.spyOn(console, "info").mockImplementation(() => {});
  });
  afterEach(() => jest.restoreAllMocks());

  it("asks the Android module for the call's route and gives it back once", async () => {
    const native = callAudioModule();
    nativeModule.mockImplementation((name: string) => (name === "RecallCallAudio" ? native : null));

    const route = await startCallAudio();
    expect(native.startAsync).toHaveBeenCalledTimes(1);

    route.stop();
    route.stop();
    expect(native.stopAsync).toHaveBeenCalledTimes(1);
  });

  it("keeps the live call's route when a stale call hangs up after it", async () => {
    const native = callAudioModule();
    nativeModule.mockReturnValue(native);

    const stale = await startCallAudio();
    const live = await startCallAudio();
    stale.stop();
    // The call hung up while it connected let go after the next one routed: the route stays.
    expect(native.stopAsync).not.toHaveBeenCalled();

    live.stop();
    expect(native.stopAsync).toHaveBeenCalledTimes(1);
  });

  it("leaves the route alone in a build without the module (iOS, Expo Go, before a rebuild)", async () => {
    nativeModule.mockReturnValue(null);
    const route = await startCallAudio();
    expect(() => route.stop()).not.toThrow();
  });

  it("takes another module answering to the name for none", async () => {
    // Tests and old builds answer every name with whatever module they have.
    nativeModule.mockReturnValue({ isDevice: true });
    const route = await startCallAudio();
    expect(() => route.stop()).not.toThrow();
  });

  it("says when a phone call or another app takes the audio, only while the route is held", async () => {
    const native = callAudioModule();
    nativeModule.mockReturnValue(native);
    const onInterrupted = jest.fn();

    const route = await startCallAudio(onInterrupted);
    native.interrupt();
    expect(onInterrupted).toHaveBeenCalledTimes(1);

    route.stop();
    native.interrupt();
    expect(onInterrupted).toHaveBeenCalledTimes(1);
  });

  it("refuses the call while the phone is on one, holding nothing", async () => {
    const native = callAudioModule();
    native.startAsync.mockRejectedValueOnce(
      Object.assign(new Error("The phone is on a call"), { code: "ERR_AUDIO_FOCUS_REFUSED" }),
    );
    nativeModule.mockReturnValue(native);
    const onInterrupted = jest.fn();

    await expect(startCallAudio(onInterrupted)).rejects.toThrow("phone_busy");
    native.interrupt();
    expect(onInterrupted).not.toHaveBeenCalled();

    // The refused call let go of its count: the next call is the only holder, and its hang-up unroutes.
    native.stopAsync.mockClear();
    const next = await startCallAudio();
    next.stop();
    expect(native.stopAsync).toHaveBeenCalledTimes(1);
  });

  it("routes a build whose module sends no events", async () => {
    const native: Partial<ReturnType<typeof callAudioModule>> = callAudioModule();
    delete native.addListener;
    nativeModule.mockReturnValue(native);

    const route = await startCallAudio(jest.fn());
    expect(native.startAsync).toHaveBeenCalledTimes(1);
    route.stop();
    expect(native.stopAsync).toHaveBeenCalledTimes(1);
  });

  it("still connects the call, on the phone's own route, when routing fails", async () => {
    const native = callAudioModule();
    native.startAsync.mockRejectedValueOnce(new Error("audio service died"));
    native.stopAsync.mockRejectedValueOnce(new Error("audio service died"));
    nativeModule.mockReturnValue(native);

    const route = await startCallAudio();
    route.stop();
    await flush();

    expect(native.stopAsync).toHaveBeenCalledTimes(1);
    expect(console.info).toHaveBeenCalledWith("[LiveTalk/audio]", { stage: "start", error: "Error" });
    expect(console.info).toHaveBeenCalledWith("[LiveTalk/audio]", { stage: "stop", error: "Error" });
  });
});
