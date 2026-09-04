import Constants, { ExecutionEnvironment } from "expo-constants";

function isDevClientBuild(): boolean {
  try {
    // Optional — present after `expo install expo-dev-client` + native rebuild.
    const devClient = require("expo-dev-client") as {
      isDevelopmentBuild?: () => boolean;
    };
    return devClient.isDevelopmentBuild?.() === true;
  } catch {
    return false;
  }
}

/** True when running inside the Expo Go app (not a dev/production build). */
export function isExpoGo(): boolean {
  if (isDevClientBuild()) return false;

  const env = Constants.executionEnvironment;
  if (
    env === ExecutionEnvironment.Bare ||
    env === ExecutionEnvironment.Standalone
  ) {
    return false;
  }

  // StoreClient covers Expo Go and some dev clients; only Expo Go sets appOwnership.
  return Constants.appOwnership === "expo";
}

/** Device GPS is only available in dev/production builds with native Info.plist keys. */
export function canUseDeviceLocation(): boolean {
  return !isExpoGo();
}

/**
 * Dictation uses expo-audio, which is included in Expo Go. Live Talk still
 * needs WebRTC in a custom Recall build — that is gated separately.
 */
export function canUseVoiceInput(): boolean {
  return true;
}
