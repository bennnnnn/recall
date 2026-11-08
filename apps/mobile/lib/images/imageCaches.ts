import { Image } from "expo-image";

/**
 * Forgets every picture expo-image has kept, decoded in memory and as files on disk. The
 * account's photos, gallery, avatar and chat images are drawn with `cachePolicy="memory-disk"`,
 * so without this they stay on the phone after it signs out. Best-effort: never rejects.
 */
export async function clearImageCaches(): Promise<void> {
  await Promise.allSettled([Image.clearMemoryCache(), Image.clearDiskCache()]);
}
