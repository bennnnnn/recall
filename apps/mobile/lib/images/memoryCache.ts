import { Image } from "expo-image";
import { Platform } from "react-native";

/**
 * The most decoded images (bytes) iOS keeps in memory between uses. expo-image keeps
 * every picture it has drawn, decoded, in SDWebImage's memory cache, and that cache
 * has no limit until the system warns of low memory: over one session of photo
 * strips, attached photos, the viewer and avatars it grew by hundreds of MB.
 * About a dozen full-screen photos, or hundreds of chat thumbnails.
 */
export const IMAGE_MEMORY_COST_BYTES = 64 * 1024 * 1024;
/** The most images it keeps, whatever their size (favicons and avatars are many). */
export const IMAGE_MEMORY_COUNT = 150;

/**
 * Bounds the decoded-image memory cache. A picture on screen keeps its own copy; one
 * evicted is read back from the disk cache when it is shown again. Android's cache
 * (Glide) already sizes itself to the device.
 */
export function boundImageMemoryCache(): void {
  if (Platform.OS !== "ios") return;
  Image.configureCache({
    maxMemoryCost: IMAGE_MEMORY_COST_BYTES,
    maxMemoryCount: IMAGE_MEMORY_COUNT,
  });
}
