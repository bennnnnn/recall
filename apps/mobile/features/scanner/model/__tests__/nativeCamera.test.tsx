import { TurboModuleRegistry } from "react-native";
import { NitroModules } from "react-native-nitro-modules";

import { nativeScannerLinked } from "@/features/scanner/model/nativeCamera";
import { isExpoGo } from "@/lib/expoRuntime";

jest.mock("react-native-nitro-modules", () => ({
  NitroModules: { hasHybridObject: jest.fn() },
}));

jest.mock("@/lib/expoRuntime", () => ({ isExpoGo: jest.fn(() => false) }));

const hasHybridObject = jest.mocked(NitroModules.hasHybridObject);

afterEach(() => jest.restoreAllMocks());

it("is false without Nitro's own native module, before Nitro loads (Expo Go)", async () => {
  jest.spyOn(TurboModuleRegistry, "get").mockReturnValue(null);
  await expect(nativeScannerLinked()).resolves.toBe(false);
  expect(hasHybridObject).not.toHaveBeenCalled();
});

it("is false in Expo Go even with a Nitro native module, before Nitro loads", async () => {
  // Expo Go ships a Nitro of its own whose version differs from ours: loading ours throws.
  jest.mocked(isExpoGo).mockReturnValueOnce(true);
  jest.spyOn(TurboModuleRegistry, "get").mockReturnValue({} as never);
  await expect(nativeScannerLinked()).resolves.toBe(false);
  expect(hasHybridObject).not.toHaveBeenCalled();
});

it.each([
  [["CameraFactory", "VisionCameraMLKit"], true],
  // The Simulator build links ML Kit out.
  [["CameraFactory"], false],
  [[], false],
])("with Nitro, needs both the camera and ML Kit: %j -> %s", async (linked, expected) => {
  jest.spyOn(TurboModuleRegistry, "get").mockReturnValue({} as never);
  hasHybridObject.mockImplementation((name: string) => linked.includes(name));
  await expect(nativeScannerLinked()).resolves.toBe(expected);
});
