import { Platform, Vibration } from 'react-native';

/**
 * Light tactile feedback for key actions.
 *
 * Android gets a short vibration via the built-in API. iOS is intentionally a
 * no-op: `Vibration` on iOS is a heavy buzz, not a subtle tap. Proper iOS
 * haptics (impact/selection) need `expo-haptics` — see FEATURES.md. When that's
 * added, swap the body here and every call site upgrades automatically.
 */
export function tap(): void {
  if (Platform.OS === 'android') {
    Vibration.vibrate(10);
  }
}
