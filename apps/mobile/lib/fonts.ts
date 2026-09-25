import { Platform } from "react-native";

/** SpaceMono from @expo-google-fonts/space-mono. Registered in _layout without blocking first paint. */
export const CODE_FONT = "SpaceMono";

/**
 * Serif face for formulas and calculation steps so they scan apart from
 * body prose. System faces only — no extra font download on the chat path.
 */
export const MATH_FONT = Platform.select({
  ios: "Georgia",
  android: "serif",
  default: "Georgia",
});
