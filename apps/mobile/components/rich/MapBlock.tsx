import { useMemo, useState } from "react";
import { type LayoutChangeEvent, StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Path, Rect } from "react-native-svg";

import { VisualCard } from "@/components/rich/VisualCard";
import i18n from "@/lib/i18n";
import {
  countriesIn,
  countryAt,
  countryPath,
  formatCoordinates,
  mapView,
  parseMapFence,
} from "@/lib/map/mapFence";
import { Space } from "@/lib/space";
import { type Theme, useTheme, withAlpha } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = { content: string };

/** "Where is Kenya?": the place on an offline map, its country tinted, a pin on the point. */
export function MapBlock({ content }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [width, setWidth] = useState(0);
  const fence = useMemo(() => parseMapFence(content), [content]);
  const drawn = useMemo(() => {
    if (!fence) return null;
    const found = countryAt(fence.lat, fence.lon);
    const view = mapView(fence, found?.polygon ?? null);
    const shapes = countriesIn(view).map((country) => ({
      key: country.id + country.name,
      d: countryPath(country),
      home: country === found?.country,
    }));
    return { found, view, shapes };
  }, [fence]);

  if (!fence || !drawn) {
    return (
      <View style={s.fallback}>
        <Text style={s.fallbackText}>{i18n.t("rich.map_error")}</Text>
      </View>
    );
  }

  const { view, shapes, found } = drawn;
  const height = (width * view.height) / view.width;
  // Strokes and the pin are in map units, so they scale with the view.
  const unit = view.height / 100;
  const caption = [found?.country.name, formatCoordinates(fence.lat, fence.lon)]
    .filter((part) => part && part !== fence.place)
    .join(" · ");

  return (
    <VisualCard label={fence.place} icon="map-pin">
      <View
        style={s.map}
        onLayout={(event: LayoutChangeEvent) => setWidth(event.nativeEvent.layout.width)}
        accessible
        accessibilityRole="image"
        accessibilityLabel={i18n.t("rich.map_a11y", { place: fence.place })}
      >
        {width > 0 ? (
          <Svg
            width={width}
            height={height}
            viewBox={`${view.minX} ${view.minY} ${view.width} ${view.height}`}
            preserveAspectRatio="xMidYMid slice"
          >
            <Rect
              x={view.minX - view.width}
              y={view.minY - view.height}
              width={view.width * 3}
              height={view.height * 3}
              fill={theme.surfaceAlt}
            />
            {shapes.map((shape) => (
              <Path
                key={shape.key}
                d={shape.d}
                fillRule="evenodd"
                fill={shape.home ? withAlpha(theme.primary, 0.35) : theme.border}
                stroke={shape.home ? theme.primary : theme.bg}
                strokeWidth={shape.home ? unit * 0.5 : unit * 0.25}
              />
            ))}
            <Circle
              cx={fence.lon}
              cy={-fence.lat}
              r={unit * 2.2}
              fill={theme.primary}
              stroke={theme.bg}
              strokeWidth={unit * 0.8}
            />
          </Svg>
        ) : null}
      </View>
      {caption ? <Text style={s.caption}>{caption}</Text> : null}
    </VisualCard>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    map: { width: "100%", minHeight: 120, backgroundColor: t.surfaceAlt },
    caption: {
      ...Type.caption,
      color: t.textSecondary,
      paddingHorizontal: Space.md,
      paddingVertical: Space.xs,
    },
    fallback: { paddingVertical: Space.sm },
    fallbackText: { ...Type.secondary, color: t.textSecondary },
  });
}
