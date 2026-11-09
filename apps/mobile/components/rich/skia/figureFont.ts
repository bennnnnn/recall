import { useMemo } from "react";
import { Platform } from "react-native";
import { matchFont, useFont, type SkFont } from "@shopify/react-native-skia";

import { Type } from "@/lib/type";

/**
 * The UI face by the name Skia's font manager knows it. iOS maps "System" to San Francisco;
 * Android's manager reads the phone's font list, where Roboto is "sans-serif" and "System"
 * names nothing, so a font matched by it draws nothing.
 */
function systemFamily(): string {
  return Platform.OS === "ios" ? Type.meta.fontFamily : "sans-serif";
}

/** A face that draws nothing (a family the manager lacks) has no glyph for "0". */
function drawsDigits(font: SkFont): boolean {
  return (font.getGlyphIDs("0")[0] ?? 0) !== 0;
}

/**
 * Letters placed at their true widths. By default a face rounds each glyph's advance to a
 * whole point, so a 12pt label drew with uneven gaps on a dense screen ("Veloc ity").
 */
function evenlySpaced(font: SkFont): SkFont {
  font.setSubpixel(true);
  font.setLinearMetrics(true);
  return font;
}

/**
 * The app's own face for the words and numbers on a figure's canvas (a graph's axes, a
 * scene's labels), at the figure's label `size`: the meta role's weight (`lib/type`) in the
 * system's UI face. Nothing loads, so the labels draw with the figure, and the face carries
 * Greek. `HaloText` sets its digits tabular. On a phone whose font manager has no such face
 * the diagrams' bundled sans is loaded instead, and labels wait for it (null until then).
 */
export function useFigureFont(size: number): SkFont | null {
  const system = useMemo(() => {
    // matchFont reads the role's family and weight; the size is the figure's.
    const font = matchFont({ ...Type.meta, fontFamily: systemFamily(), fontStyle: "normal", fontSize: size });
    return drawsDigits(font) ? evenlySpaced(font) : null;
  }, [size]);
  const loaded = useFont(
    system ? null : require("@expo-google-fonts/source-sans-3/400Regular/SourceSans3_400Regular.ttf"),
    size,
  );
  const bundled = useMemo(() => (loaded ? evenlySpaced(loaded) : null), [loaded]);
  return system ?? bundled;
}
