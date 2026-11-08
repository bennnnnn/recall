import { requireOptionalNativeModule } from "expo-modules-core";

/**
 * Where live talk's voice plays. react-native-webrtc plays it as a phone call and leaves the
 * route to the app, and Android sends a call to the earpiece: held in the hand, the reply was
 * barely audible. On Android, `modules/call-audio` plays the call through a connected headset,
 * else the loudspeaker, for as long as it lasts. iOS routes it already and has no such module;
 * neither has a build made before it (Expo Go included), which keeps the old route.
 *
 * Live talk never calls expo-audio's `setAudioModeAsync` during a call: on Android it resets the
 * mode and turns the speakerphone on. From Android 12 the module takes the route back, though
 * the voice jumps; before it, the call would stay off its route.
 *
 * A phone call comes first: the module refuses a call while the phone is on one (`phone_busy`),
 * and says when one, or another app, takes the audio mid-call (`onInterrupted`).
 */
type Subscription = { remove: () => void };
type CallAudioModule = {
  startAsync: () => Promise<void>;
  stopAsync: () => Promise<void>;
  /** The native module's events; a build made before them has none. */
  addListener?: (event: "onInterrupted", listener: () => void) => Subscription;
};

/** A call's hold on the route: stop lets go of it, once. */
type CallAudio = { stop: () => void };

/** The module's rejection when Android refused the call its audio focus: the phone is on a call. */
const FOCUS_REFUSED = "ERR_AUDIO_FOCUS_REFUSED";

/**
 * The phone has one route and every call shares it: the calls holding it now. A call hung up
 * while it still connected lets go after the next one took the route, and only the last call
 * to let go gives the route back, so a stale call's hang-up never unroutes the live one.
 */
let holders = 0;

function loadCallAudio(): CallAudioModule | null {
  const native = requireOptionalNativeModule<Partial<CallAudioModule>>("RecallCallAudio");
  return typeof native?.startAsync === "function" && typeof native.stopAsync === "function"
    ? (native as CallAudioModule)
    : null;
}

function logRouteFailed(stage: "start" | "stop" | "listen", error: unknown): void {
  console.info("[LiveTalk/audio]", { stage, error: error instanceof Error ? error.name : typeof error });
}

function listenForInterruption(native: CallAudioModule, onInterrupted: () => void): Subscription | null {
  try {
    return native.addListener?.("onInterrupted", onInterrupted) ?? null;
  } catch (error) {
    // A build without the event still routes the call; it only cannot hear an interruption.
    logRouteFailed("listen", error);
    return null;
  }
}

function focusRefused(error: unknown): boolean {
  return typeof error === "object" && error !== null && (error as { code?: unknown }).code === FOCUS_REFUSED;
}

/**
 * Route the call before WebRTC opens the mic, so its audio starts on the call's route.
 * `onInterrupted` runs while the route is held, when a phone call or another app takes the audio.
 * Rejects with `phone_busy`, holding nothing, while the phone is on a call.
 */
export async function startCallAudio(onInterrupted: () => void = () => undefined): Promise<CallAudio> {
  const native = loadCallAudio();
  if (!native) return { stop: () => undefined };
  holders += 1;
  let held = true;
  // Before the route is taken: focus can be lost as soon as it is granted.
  const interruption = listenForInterruption(native, onInterrupted);
  const hold: CallAudio = {
    stop: () => {
      if (!held) return;
      held = false;
      interruption?.remove();
      holders -= 1;
      if (holders > 0) return;
      native.stopAsync().catch((error: unknown) => logRouteFailed("stop", error));
    },
  };
  try {
    // Each call asks again: the module keeps one route and sets its mode and device once more.
    await native.startAsync();
  } catch (error) {
    if (focusRefused(error)) {
      // The module took neither the mode nor the route: the call must not start over the phone call.
      hold.stop();
      throw new Error("phone_busy");
    }
    // The call still connects, on the phone's own route.
    logRouteFailed("start", error);
  }
  return hold;
}
