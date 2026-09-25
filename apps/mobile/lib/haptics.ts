import { Platform, Vibration } from "react-native";
import * as Haptics from "expo-haptics";

/** Platform where native haptics failed. Vibration is the Android fallback only. */
let unavailableOn: string | null = null;

function vibrateAndroid(ms: number): void {
  if (Platform.OS !== "android") return;
  try {
    Vibration.vibrate(ms);
  } catch {
    /* ignore */
  }
}

function play(fn: () => Promise<void>, androidFallbackMs: number): void {
  if (unavailableOn === Platform.OS) {
    vibrateAndroid(androidFallbackMs);
    return;
  }
  let pending: Promise<void>;
  try {
    pending = Promise.resolve(fn());
  } catch {
    unavailableOn = Platform.OS;
    vibrateAndroid(androidFallbackMs);
    return;
  }
  void pending
    .then(() => {
      unavailableOn = null;
    })
    .catch(() => {
      unavailableOn = Platform.OS;
      vibrateAndroid(androidFallbackMs);
    });
}

/** @internal Resets the Expo Go miss cache between tests. */
export function resetHapticsAvailabilityForTests(): void {
  unavailableOn = null;
}

/** Light tactile feedback for an important press. Never throws. */
export function tap(): void {
  play(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light), 10);
}

/** Picker / toggle feedback. */
export function selection(): void {
  play(() => Haptics.selectionAsync(), 8);
}

/** Camera shutter / other medium impacts. */
export function impactMedium(): void {
  play(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium), 18);
}

/** One confirmation. Copy, a finished answer, a completed task. */
export function notifySuccess(): void {
  play(
    () => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success),
    12,
  );
}

/** Validation, a failed send, or a confirmed destructive action. */
export function notifyWarning(): void {
  play(
    () => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning),
    16,
  );
}

/**
 * Feedback for a confirmed destructive action. Call once, after the
 * destructive operation succeeds — never when opening or cancelling an alert.
 */
export function notifyDestructive(): void {
  notifyWarning();
}
