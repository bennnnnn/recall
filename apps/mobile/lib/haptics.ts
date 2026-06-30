import { Platform, Vibration } from "react-native";
import * as Haptics from "expo-haptics";

/** Cached after first call — false when native haptics aren't linked (e.g. Expo Go). */
let iosHapticsAvailable: boolean | null = null;

async function runIosHaptic(fn: () => Promise<void>): Promise<void> {
  if (iosHapticsAvailable === false) return;
  try {
    await fn();
    iosHapticsAvailable = true;
  } catch {
    iosHapticsAvailable = false;
  }
}

/** Light tactile feedback for key actions. Never throws — safe in Expo Go. */
export function tap(): void {
  if (Platform.OS === "ios") {
    void runIosHaptic(() =>
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light),
    );
    return;
  }
  if (Platform.OS === "android") {
    try {
      Vibration.vibrate(10);
    } catch {
      /* ignore */
    }
  }
}

/** Picker / toggle feedback (iOS selection click). */
export function selection(): void {
  if (Platform.OS === "ios") {
    void runIosHaptic(() => Haptics.selectionAsync());
    return;
  }
  tap();
}

/** Positive confirmation — copy succeeded, thumbs up, etc. */
export function notifySuccess(): void {
  if (Platform.OS === "ios") {
    void runIosHaptic(() =>
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success),
    );
    return;
  }
  tap();
}

/** Destructive or negative confirmation — thumbs down, errors. */
export function notifyWarning(): void {
  if (Platform.OS === "ios") {
    void runIosHaptic(() =>
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning),
    );
    return;
  }
  tap();
}
