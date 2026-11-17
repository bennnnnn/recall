import { TurboModuleRegistry } from "react-native";

import { isExpoGo } from "@/lib/expoRuntime";

/**
 * The Nitro objects the live scanner creates as its modules load: VisionCamera's camera
 * factory and ML Kit's text reader. The Simulator build links ML Kit out
 * (`react-native.config.js`), and Expo Go has neither.
 */
const SCANNER_HYBRID_OBJECTS = ["CameraFactory", "VisionCameraMLKit"] as const;

/**
 * Whether this build can load the live scanner, asked before its modules are.
 *
 * Loading them where one is missing does not reject the dynamic import: Metro's `require`
 * reports a module that throws while it loads to ErrorUtils as a fatal error and returns
 * nothing, so `import()` resolves to a module without its exports. Nitro is asked first,
 * and only when its own native module is in the build and is ours: Expo Go ships a Nitro of
 * its own (0.37.1 beside our 0.37.2), whose version check throws as our Nitro loads, and it
 * never holds the scanner's objects, so Expo Go is never asked.
 */
export async function nativeScannerLinked(): Promise<boolean> {
  return hybridObjectsLinked(SCANNER_HYBRID_OBJECTS);
}

/** Whether ML Kit's text reader is in this build, to read a still with (`readTextLines`). */
export async function textReaderLinked(): Promise<boolean> {
  return hybridObjectsLinked(["VisionCameraMLKit"]);
}

async function hybridObjectsLinked(names: readonly string[]): Promise<boolean> {
  if (isExpoGo() || TurboModuleRegistry.get("NitroModules") == null) return false;
  const { NitroModules } = await import("react-native-nitro-modules");
  return names.every((name) => NitroModules.hasHybridObject(name));
}
