import { Platform, Vibration } from "react-native";
import * as Haptics from "expo-haptics";

/** Cached after first call — false when native haptics aren't linked (e.g. Expo Go). */
let iosHapticsAvailable: boolean | null = null;

async function iosTap(): Promise<void> {
  if (iosHapticsAvailable === false) return;
  try {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    iosHapticsAvailable = true;
  } catch {
    iosHapticsAvailable = false;
  }
}

/** Light tactile feedback for key actions. Never throws — safe in Expo Go. */
export function tap(): void {
  if (Platform.OS === "ios") {
    void iosTap();
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
