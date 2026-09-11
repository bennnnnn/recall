import { loadLastPhotoUri } from "@/lib/lastPhotoThumbnail";
import { getPermissionsAsync } from "expo-media-library";
import { getAssetsAsync } from "expo-media-library/legacy";

jest.mock("expo-media-library", () => ({
  getPermissionsAsync: jest.fn(),
}));

jest.mock("expo-media-library/legacy", () => ({
  getAssetsAsync: jest.fn(),
}));

it("returns null when library permission is not granted", async () => {
  jest.mocked(getPermissionsAsync).mockResolvedValue({ granted: false } as Awaited<
    ReturnType<typeof getPermissionsAsync>
  >);
  await expect(loadLastPhotoUri()).resolves.toBeNull();
  expect(getAssetsAsync).not.toHaveBeenCalled();
});

it("returns the newest photo uri when permission is already granted", async () => {
  jest.mocked(getPermissionsAsync).mockResolvedValue({ granted: true } as Awaited<
    ReturnType<typeof getPermissionsAsync>
  >);
  jest.mocked(getAssetsAsync).mockResolvedValue({
    assets: [{ uri: "ph://1" }],
  } as Awaited<ReturnType<typeof getAssetsAsync>>);
  await expect(loadLastPhotoUri()).resolves.toBe("ph://1");
});
