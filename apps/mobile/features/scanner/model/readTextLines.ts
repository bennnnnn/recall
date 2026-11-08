import { deleteAsync } from "expo-file-system/legacy";

import type { ImageBox } from "@/features/scanner/model/contentFit";
import { textReaderLinked } from "@/features/scanner/model/nativeCamera";
import { shrinkScanImage } from "@/features/scanner/model/scanImage";

/**
 * ML Kit reads a still of at most 4 MP on Android; a copy this long on its long side stays
 * under that at any shape (a 2048 px square is 4.2 MP and is refused).
 */
const READ_MAX_EDGE = 1600;

/**
 * The text lines ML Kit finds in a still, as ratios of it, read on the phone; nothing is
 * sent. Empty where this build has no ML Kit (Expo Go, the Simulator) or the read fails,
 * and the crop frame then stays where it was. Both platforms read the still upright, as
 * `measureScanImage` measures it.
 */
export async function readTextLines(uri: string, size: { width: number; height: number }): Promise<ImageBox[]> {
  let copy: string | null = null;
  try {
    if (!(await textReaderLinked())) return [];
    let read = { uri, ...size };
    if (Math.max(size.width, size.height) > READ_MAX_EDGE) {
      read = await shrinkScanImage(uri, READ_MAX_EDGE);
      copy = read.uri;
    }
    const { processImageTextRecognition } = await import("react-native-vision-camera-mlkit");
    const result = await processImageTextRecognition(read.uri);
    return result.blocks
      .flatMap((block) => block.lines)
      .filter((line) => line.text.trim().length > 0)
      .map(({ bounds }) => ({
        // From the edges, whichever way round: the plugin names a line's bottom edge `top`
        // on iOS (`top: bounds.maxY`), and its top edge `top` on Android.
        x: Math.min(bounds.left, bounds.right) / read.width,
        y: Math.min(bounds.top, bounds.bottom) / read.height,
        width: Math.abs(bounds.right - bounds.left) / read.width,
        height: Math.abs(bounds.bottom - bounds.top) / read.height,
      }));
  } catch (error) {
    console.warn("[scanner] could not read the still's text", error instanceof Error ? error.message : typeof error);
    return [];
  } finally {
    if (copy) {
      void deleteAsync(copy, { idempotent: true }).catch((error: unknown) =>
        console.warn("[scanner] could not delete a read copy", error instanceof Error ? error.name : typeof error));
    }
  }
}
