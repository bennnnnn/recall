import Svg, { Circle, G, Line, Path, Rect } from "react-native-svg";

import { Icon } from "@/components/Icon";
import type { IoniconName } from "@/lib/icons";

/** Lucide-style outline weight — a bit heavier than Ionicons, closer to ChatGPT. */
export const MENU_ICON_STROKE = 2.25;

export type StrokeIconName =
  | "share"
  | "pin"
  | "archive"
  | "file-text"
  | "pencil"
  | "trash"
  | "checkbox"
  | "undo"
  | "scan"
  | "camera"
  | "image"
  | "file";

type Props = {
  name: StrokeIconName;
  color: string;
  size?: number;
};

const strokeProps = (color: string) => ({
  stroke: color,
  strokeWidth: MENU_ICON_STROKE,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  fill: "none" as const,
});

/**
 * Outline glyphs for action sheets and share/pin/archive controls.
 * Ionicons is a font — it cannot thicken stroke — so these are SVG.
 */
export function StrokeIcon({ name, color, size = 20 }: Props) {
  const s = strokeProps(color);
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      {glyph(name, s, color)}
    </Svg>
  );
}

export function ShareNodesIcon({ size = 20, color }: { size?: number; color: string }) {
  return <StrokeIcon name="share" size={size} color={color} />;
}

export function PinTiltIcon({ size = 20, color }: { size?: number; color: string }) {
  return <StrokeIcon name="pin" size={size} color={color} />;
}

export function ArchiveBoxIcon({ size = 20, color }: { size?: number; color: string }) {
  return <StrokeIcon name="archive" size={size} color={color} />;
}

/** Toast / banner: reuse the same share / pin / archive glyphs. */
export function BannerGlyph({
  name,
  size,
  color,
}: {
  name: IoniconName;
  size: number;
  color: string;
}) {
  const stroke = BANNER_STROKE[name];
  if (stroke) return <StrokeIcon name={stroke} size={size} color={color} />;
  return <Icon name={name} size={size} color={color} />;
}

const BANNER_STROKE: Partial<Record<IoniconName, StrokeIconName>> = {
  "share-outline": "share",
  pin: "pin",
  "pin-outline": "pin",
  bookmark: "pin",
  "bookmark-outline": "pin",
  "archive-outline": "archive",
};

type Stroke = ReturnType<typeof strokeProps>;

function glyph(name: StrokeIconName, s: Stroke, color: string) {
  switch (name) {
    case "share":
      return (
        <>
          <Circle cx="18" cy="5" r="3" stroke={color} strokeWidth={MENU_ICON_STROKE} fill="none" />
          <Circle cx="6" cy="12" r="3" stroke={color} strokeWidth={MENU_ICON_STROKE} fill="none" />
          <Circle cx="18" cy="19" r="3" stroke={color} strokeWidth={MENU_ICON_STROKE} fill="none" />
          <Line x1="8.59" y1="13.51" x2="15.42" y2="17.49" {...s} />
          <Line x1="15.41" y1="6.51" x2="8.59" y2="10.49" {...s} />
        </>
      );
    case "pin":
      return (
        <G transform="rotate(-40 12 12)">
          <Path d="M12 17v5" {...s} />
          <Path
            d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"
            {...s}
          />
        </G>
      );
    case "archive":
      return (
        <>
          <Rect width="20" height="5" x="2" y="3" rx="1" {...s} />
          <Path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8" {...s} />
          <Path d="M10 12h4" {...s} />
        </>
      );
    case "file-text":
      return (
        <>
          <Path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" {...s} />
          <Path d="M14 2v6h6" {...s} />
          <Path d="M16 13H8" {...s} />
          <Path d="M16 17H8" {...s} />
          <Path d="M10 9H8" {...s} />
        </>
      );
    case "pencil":
      return (
        <>
          <Path
            d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"
            {...s}
          />
          <Path d="m15 5 4 4" {...s} />
        </>
      );
    case "trash":
      return (
        <>
          <Path d="M3 6h18" {...s} />
          <Path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" {...s} />
          <Path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" {...s} />
          <Line x1="10" y1="11" x2="10" y2="17" {...s} />
          <Line x1="14" y1="11" x2="14" y2="17" {...s} />
        </>
      );
    case "checkbox":
      return (
        <>
          <Rect width="18" height="18" x="3" y="3" rx="2" {...s} />
          <Path d="m9 12 2 2 4-4" {...s} />
        </>
      );
    case "undo":
      return (
        <>
          <Path d="M9 14 4 9l5-5" {...s} />
          <Path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5 5.5 5.5 0 0 1-5.5 5.5H11" {...s} />
        </>
      );
    case "scan":
      return (
        <>
          <Path d="M3 7V5a2 2 0 0 1 2-2h2" {...s} />
          <Path d="M17 3h2a2 2 0 0 1 2 2v2" {...s} />
          <Path d="M21 17v2a2 2 0 0 1-2 2h-2" {...s} />
          <Path d="M7 21H5a2 2 0 0 1-2-2v-2" {...s} />
          <Path d="M7 12h10" {...s} />
        </>
      );
    case "camera":
      return (
        <>
          <Path
            d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"
            {...s}
          />
          <Circle cx="12" cy="13" r="3" stroke={color} strokeWidth={MENU_ICON_STROKE} fill="none" />
        </>
      );
    case "image":
      return (
        <>
          <Rect width="18" height="18" x="3" y="3" rx="2" {...s} />
          <Circle cx="9" cy="9" r="2" stroke={color} strokeWidth={MENU_ICON_STROKE} fill="none" />
          <Path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" {...s} />
        </>
      );
    case "file":
      return (
        <>
          <Path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" {...s} />
          <Path d="M14 2v6h6" {...s} />
        </>
      );
  }
}
