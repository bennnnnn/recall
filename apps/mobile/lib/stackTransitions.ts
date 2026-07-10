import { Platform } from "react-native";

/** Shared native-stack transition presets for expo-router screens. */

export type StackTransitionPreset = {
  animation?:
    | "default"
    | "fade"
    | "fade_from_bottom"
    | "slide_from_right"
    | "slide_from_bottom"
    | "none";
  gestureEnabled?: boolean;
  fullScreenGestureEnabled?: boolean;
  animationDuration?: number;
};

/** Hierarchical push (settings drill-down, projects, memory, todos). */
export function stackPushTransition(): StackTransitionPreset {
  return {
    animation: Platform.OS === "ios" ? "default" : "slide_from_right",
    gestureEnabled: true,
    fullScreenGestureEnabled: Platform.OS === "ios",
    animationDuration: 280,
  };
}

/** Utility screens opened from the drawer / home (slight lift). */
export function stackUtilityTransition(): StackTransitionPreset {
  return {
    animation: "fade_from_bottom",
    gestureEnabled: true,
    fullScreenGestureEnabled: Platform.OS === "ios",
    animationDuration: 320,
  };
}

/** Onboarding and login — soft cross-fade instead of a hard slide. */
export function stackAuthTransition(): StackTransitionPreset {
  return {
    animation: "fade",
    gestureEnabled: false,
    animationDuration: 240,
  };
}

/** Chat home — avoid animating the primary surface on cold start / redirects. */
export function stackHomeTransition(): StackTransitionPreset {
  return {
    animation: "none",
    gestureEnabled: false,
  };
}
