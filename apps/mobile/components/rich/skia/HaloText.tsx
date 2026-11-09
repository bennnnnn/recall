/**
 * Canvas text with a halo: the same string stroked in the background colour
 * first, then filled. A track, slope or arrow running behind a label is then
 * interrupted around it instead of striking it through.
 *
 * With `fallbacks`, a character the main font cannot draw is set in the first
 * fallback that can. Digits a face draws at different widths are set tabular
 * (`fontRuns.ts`).
 */
import { useMemo, type ComponentProps } from "react";
import { Glyphs, Group, Text as SkiaText, type SkFont } from "@shopify/react-native-skia";
import { useDerivedValue } from "react-native-reanimated";

import { fontRuns, needsFallback, needsTabular, tabularGlyphs } from "@/components/rich/skia/fontRuns";

const HALO_WIDTH = 3;
const HALO_PAINT = { style: "stroke", strokeWidth: HALO_WIDTH, strokeJoin: "round" } as const;

type Coordinate = ComponentProps<typeof SkiaText>["x"];

type Props = {
  x: Coordinate;
  y: Coordinate;
  text: string;
  /** Null while the label's face loads: the label waits for it. */
  font: SkFont | null;
  color: string;
  /** The surface behind the canvas (`theme.bg`). */
  halo: string;
  /** Fonts tried, in order, for characters `font` has no glyph for. */
  fallbacks?: readonly (SkFont | null)[];
};

type LabelProps = Omit<Props, "fallbacks" | "font"> & { font: SkFont };

export function HaloText({ fallbacks, font, ...props }: Props) {
  const fonts = useMemo(
    () => (font ? [font, ...(fallbacks ?? []).filter((face): face is SkFont => face !== null)] : []),
    [fallbacks, font],
  );
  const split = useMemo(
    () => fonts.length > 1 && needsFallback(props.text, fonts),
    [fonts, props.text],
  );
  if (!font) return null;
  return split ? <HaloRuns {...props} font={font} fonts={fonts} /> : <HaloLine {...props} font={font} />;
}

/** One font's ink for `text`: plain text, or glyphs placed in cells when its digits vary. */
function Ink({
  x,
  y,
  text,
  font,
  color,
  halo = false,
}: { x: Coordinate; y: Coordinate; text: string; font: SkFont; color: string; halo?: boolean }) {
  const glyphs = useMemo(() => (needsTabular(font, text) ? tabularGlyphs(font, text).glyphs : null), [font, text]);
  const paint = halo ? HALO_PAINT : null;
  return glyphs ? (
    <Glyphs x={x} y={y} font={font} glyphs={glyphs} color={color} {...paint} />
  ) : (
    <SkiaText x={x} y={y} text={text} font={font} color={color} {...paint} />
  );
}

function HaloLine({ x, y, text, font, color, halo }: LabelProps) {
  return (
    <>
      <Ink x={x} y={y} text={text} font={font} color={halo} halo />
      <Ink x={x} y={y} text={text} font={font} color={color} />
    </>
  );
}

function HaloRuns({
  x,
  y,
  text,
  color,
  halo,
  fonts,
}: LabelProps & { fonts: readonly SkFont[] }) {
  const runs = useMemo(() => fontRuns(text, fonts), [fonts, text]);
  // The runs are set from the label's origin, wherever that is this frame.
  const transform = useDerivedValue(() => {
    const left = typeof x === "number" ? x : (x as { value: number }).value;
    const baseline = typeof y === "number" ? y : (y as { value: number }).value;
    return [{ translateX: left }, { translateY: baseline }];
  });
  // Every halo before any fill, so one run's halo never cuts into the run before it.
  return (
    <Group transform={transform}>
      {runs.map((run, index) => (
        <Ink key={`halo-${index}`} x={run.dx} y={0} text={run.text} font={run.font} color={halo} halo />
      ))}
      {runs.map((run, index) => (
        <Ink key={`text-${index}`} x={run.dx} y={0} text={run.text} font={run.font} color={color} />
      ))}
    </Group>
  );
}
