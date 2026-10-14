/**
 * Canvas text with a halo: the same string stroked in the background colour
 * first, then filled. A track, slope or arrow running behind a label is then
 * interrupted around it instead of striking it through.
 */
import type { ComponentProps } from "react";
import { Text as SkiaText, type SkFont } from "@shopify/react-native-skia";

const HALO_WIDTH = 3;

type Coordinate = ComponentProps<typeof SkiaText>["x"];

export function HaloText({
  x,
  y,
  text,
  font,
  color,
  halo,
}: {
  x: Coordinate;
  y: Coordinate;
  text: string;
  font: SkFont;
  color: string;
  /** The surface behind the canvas (`theme.bg`). */
  halo: string;
}) {
  return (
    <>
      <SkiaText
        x={x}
        y={y}
        text={text}
        font={font}
        color={halo}
        style="stroke"
        strokeWidth={HALO_WIDTH}
        strokeJoin="round"
      />
      <SkiaText x={x} y={y} text={text} font={font} color={color} />
    </>
  );
}
