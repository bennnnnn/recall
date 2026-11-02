import { TurboModuleRegistry } from "react-native";
import { NitroModules } from "react-native-nitro-modules";

import { nativeScannerLinked } from "@/features/scanner/model/nativeCamera";

jest.mock("react-native-nitro-modules", () => ({
  NitroModules: { hasHybridObject: jest.fn() },
}));

const hasHybridObject = jest.mocked(NitroModules.hasHybridObject);

afterEach(() => jest.restoreAllMocks());

it("is false without Nitro's own native module, before Nitro loads (Expo Go)", async () => {
  jest.spyOn(TurboModuleRegistry, "get").mockReturnValue(null);
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
