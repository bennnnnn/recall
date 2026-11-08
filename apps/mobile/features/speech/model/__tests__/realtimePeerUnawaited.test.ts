/**
 * A live call that drops (or is hung up) before `connect` awaits the connection raised
 * "Uncaught (in promise) Error: Realtime voice connection failed" over the call screen on
 * the S23 (2026-11-07). The failure still reaches `onPeerFailed`; nothing goes unhandled.
 */
import { createRealtimePeer } from "@/features/speech/model/realtimePeer";

(globalThis as { __DEV__?: boolean }).__DEV__ = false;

jest.mock("react-native", () => ({
  Platform: { OS: "android" },
  NativeModules: { WebRTCModule: {} },
  TurboModuleRegistry: { get: (name: string) => (name === "WebRTCModule" ? {} : null) },
}));
jest.mock("expo-modules-core", () => ({ requireOptionalNativeModule: () => ({ isDevice: true }) }));
jest.mock("expo-constants", () => ({}));
jest.mock("@/lib/speech/voiceAudio", () => ({ yieldMicToWebRtc: jest.fn(async () => undefined) }));
jest.mock("@/features/speech/api", () => ({
  speechApi: { createRealtimeSession: jest.fn(), connectRealtimeSession: jest.fn(), realtimeTool: jest.fn() },
}));
jest.mock("react-native-webrtc", () => ({}));

type Handler = (() => void) | null;

function fakeWebRtc() {
  const pc = {
    connectionState: "new",
    iceConnectionState: "new",
    onconnectionstatechange: null as Handler,
    oniceconnectionstatechange: null as Handler,
    ontrack: null as Handler,
    addTrack: jest.fn(),
    createDataChannel: jest.fn(() => ({ readyState: "connecting", onopen: null, onclose: null, onerror: null, onmessage: null, send: jest.fn(), close: jest.fn() })),
    close: jest.fn(),
  };
  const webrtc = {
    mediaDevices: { getUserMedia: jest.fn() },
    RTCPeerConnection: jest.fn(() => pc),
    RTCSessionDescription: jest.fn(),
  };
  const stream = { getTracks: () => [], getAudioTracks: () => [] };
  return { pc, webrtc, stream };
}

it("lets a peer that fails before anyone awaits it fail quietly, still telling its handler", async () => {
  const unhandled = jest.fn();
  process.on("unhandledRejection", unhandled);
  try {
    const { pc, webrtc, stream } = fakeWebRtc();
    const onPeerFailed = jest.fn();
    createRealtimePeer(webrtc as never, stream as never, {
      onOpen: jest.fn(),
      onMessage: jest.fn(),
      onPeerFailed,
      onChannelFailed: jest.fn(),
    });
    pc.connectionState = "failed";
    pc.onconnectionstatechange?.();
    // Let the rejection reach the runtime's unhandled check.
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
    await new Promise<void>((resolve) => setImmediate(() => resolve()));
    expect(onPeerFailed).toHaveBeenCalledWith("Realtime voice connection failed");
    expect(unhandled).not.toHaveBeenCalled();
  } finally {
    process.off("unhandledRejection", unhandled);
  }
});
