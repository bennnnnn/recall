import { requireOptionalNativeModule } from "expo-modules-core";

/**
 * Where live talk's voice plays. react-native-webrtc plays it as a phone call and leaves the
 * route to the app, and Android sends a call to the earpiece: held in the hand, the reply was
 * barely audible. On Android, `modules/call-audio` plays the call through a connected headset,
 * else the loudspeaker, for as long as it lasts. iOS routes it already and has no such module;
 * neither has a build made before it (Expo Go included), which keeps the old route.
 */
type CallAudioModule = { startAsync: () => Promise<void>; stopAsync: () => Promise<void> };

/** A call's route, held until the call ends: stop gives the phone's route back, once. */
type CallAudio = { stop: () => void };

function loadCallAudio(): CallAudioModule | null {
  const native = requireOptionalNativeModule<Partial<CallAudioModule>>("RecallCallAudio");
  return typeof native?.startAsync === "function" && typeof native.stopAsync === "function"
    ? (native as CallAudioModule)
    : null;
}

function logRouteFailed(stage: "start" | "stop", error: unknown): void {
  console.info("[LiveTalk/audio]", { stage, error: error instanceof Error ? error.name : typeof error });
}

/** Route the call before WebRTC opens the mic, so its audio starts on the call's route. */
export async function startCallAudio(): Promise<CallAudio> {
  const native = loadCallAudio();
  if (!native) return { stop: () => undefined };
  try {
    await native.startAsync();
  } catch (error) {
    // The call still connects, on the phone's own route.
    logRouteFailed("start", error);
  }
  let stopped = false;
  return {
    stop: () => {
      if (stopped) return;
      stopped = true;
      native.stopAsync().catch((error: unknown) => logRouteFailed("stop", error));
    },
  };
}
