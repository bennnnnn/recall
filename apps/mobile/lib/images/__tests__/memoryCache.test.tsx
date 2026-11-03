import { Platform } from "react-native";

import {
  IMAGE_MEMORY_COST_BYTES,
  IMAGE_MEMORY_COUNT,
  boundImageMemoryCache,
} from "@/lib/images/memoryCache";

const mockConfigureCache = jest.fn();
jest.mock("expo-image", () => ({ Image: { configureCache: (config: unknown) => mockConfigureCache(config) } }));

const os = Platform.OS;

afterEach(() => {
  mockConfigureCache.mockClear();
  Platform.OS = os;
});

// The memory cache kept every decoded picture until a low-memory warning: RAM rose by
// hundreds of MB over one session of photos.
it("bounds the decoded-image memory cache on iOS", () => {
  Platform.OS = "ios";
  boundImageMemoryCache();
  expect(mockConfigureCache).toHaveBeenCalledWith({
    maxMemoryCost: IMAGE_MEMORY_COST_BYTES,
    maxMemoryCount: IMAGE_MEMORY_COUNT,
  });
  expect(IMAGE_MEMORY_COST_BYTES).toBeGreaterThan(0);
  expect(IMAGE_MEMORY_COUNT).toBeGreaterThan(0);
});

it("leaves Android's cache, which sizes itself, alone", () => {
  Platform.OS = "android";
  boundImageMemoryCache();
  expect(mockConfigureCache).not.toHaveBeenCalled();
});

