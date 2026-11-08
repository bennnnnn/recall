import { useMemo } from "react";
import { matchFont, type SkFont } from "@shopify/react-native-skia";

import { Type } from "@/lib/type";

/**
 * The app's own face for the words and numbers on a figure's canvas (a graph's axes, a
 * scene's labels), at the figure's label `size`: the meta role's family and weight
 * (`lib/type`), which Skia takes from the system's fonts. Nothing loads, so the labels draw
 * with the figure, and the face carries Greek. `HaloText` sets its digits tabular.
 */
export function useFigureFont(size: number): SkFont {
  return useMemo(
    () =>
      // matchFont reads the role's family and weight; the size is the figure's.
      matchFont({ ...Type.meta, fontStyle: "normal", fontSize: size }),
    [size],
  );
}
