import { TurboModuleRegistry } from "react-native";

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
 * and only when its own native module is in the build.
 */
export async function nativeScannerLinked(): Promise<boolean> {
  if (TurboModuleRegistry.get("NitroModules") == null) return false;
  const { NitroModules } = await import("react-native-nitro-modules");
  return SCANNER_HYBRID_OBJECTS.every((name) => NitroModules.hasHybridObject(name));
}
