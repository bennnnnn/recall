/**
 * The ```map card: where a place is, drawn offline.
 *
 * The model writes {"place": "Kenya", "lat": 0.02, "lon": 37.91, "zoom": "country"}.
 * The app finds the country under the point itself (no name matching), frames
 * the view, and draws Natural Earth outlines from worldCountries.generated.json
 * (`pnpm world-map`). Nothing is fetched.
 */
import countriesData from "@/lib/map/worldCountries.generated.json";

export const MAP_ZOOMS = ["world", "region", "country", "city"] as const;
export type MapZoom = (typeof MAP_ZOOMS)[number];

export type MapFence = {
  place: string;
  lat: number;
  lon: number;
  zoom: MapZoom | null;
};

export type MapCountry = {
  id: string;
  name: string;
  /** Polygons → rings → flat [lon, lat, …] in tenths of a degree. */
  polygons: number[][][];
};

/** A view in map units: x = longitude, y = −latitude (degrees). */
export type MapView = { minX: number; minY: number; width: number; height: number };

const COUNTRIES = countriesData as MapCountry[];
const MAX_PLACE = 80;
/** Cards are twice as wide as tall. */
export const MAP_ASPECT = 2;
// The world view leaves out the poles: equirectangular stretches them most.
const WORLD: MapView = { minX: -180, minY: -84, width: 360, height: 144 };
const ZOOM_HEIGHT: Record<Exclude<MapZoom, "world" | "country">, number> = {
  region: 32,
  city: 6,
};
const MIN_COUNTRY_HEIGHT = 7;

function finite(value: unknown): number | null {
  const n = typeof value === "string" ? Number.parseFloat(value) : value;
  return typeof n === "number" && Number.isFinite(n) ? n : null;
}

/** The fence's place and point, or null when it is not a usable map. */
export function parseMapFence(content: string): MapFence | null {
  let raw: unknown;
  try {
    raw = JSON.parse(content);
  } catch {
    return null;
  }
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const data = raw as Record<string, unknown>;
  const place = typeof data.place === "string" ? data.place.trim() : "";
  const lat = finite(data.lat ?? data.latitude);
  const lon = finite(data.lon ?? data.lng ?? data.longitude);
  if (!place || place.length > MAX_PLACE || lat === null || lon === null) return null;
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;
  const zoom = MAP_ZOOMS.find((z) => z === data.zoom) ?? null;
  return { place, lat, lon, zoom };
}

function ringContains(ring: number[], x: number, y: number): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 2; i < ring.length; j = i, i += 2) {
    const xi = ring[i];
    const yi = ring[i + 1];
    const xj = ring[j];
    const yj = ring[j + 1];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function polygonContains(polygon: number[][], x: number, y: number): boolean {
  // Even-odd across the outer ring and its holes.
  return polygon.reduce((inside, ring) => (ringContains(ring, x, y) ? !inside : inside), false);
}

/** The country under a point and the polygon that holds it, if any. */
export function countryAt(
  lat: number,
  lon: number,
): { country: MapCountry; polygon: number[][] } | null {
  const y = lat * 10;
  // Shapes across the 180° line are unwrapped past it; try the point there too.
  for (const x of [lon * 10, (lon + 360) * 10, (lon - 360) * 10]) {
    for (const country of COUNTRIES) {
      for (const polygon of country.polygons) {
        if (polygonContains(polygon, x, y)) return { country, polygon };
      }
    }
  }
  return null;
}

type Box = { minX: number; maxX: number; minY: number; maxY: number };

function boxOf(rings: number[][]): Box {
  const box = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
  for (const ring of rings) {
    for (let i = 0; i < ring.length; i += 2) {
      const x = ring[i] / 10;
      const y = -ring[i + 1] / 10;
      box.minX = Math.min(box.minX, x);
      box.maxX = Math.max(box.maxX, x);
      box.minY = Math.min(box.minY, y);
      box.maxY = Math.max(box.maxY, y);
    }
  }
  return box;
}

const COUNTRY_BOXES = new Map(
  COUNTRIES.map((country) => [country.id + country.name, boxOf(country.polygons.flat())]),
);

function centered(x: number, y: number, height: number): MapView {
  const h = Math.min(height, WORLD.height);
  const w = Math.min(h * MAP_ASPECT, WORLD.width);
  const minY = Math.min(Math.max(y - h / 2, WORLD.minY), WORLD.minY + WORLD.height - h);
  return { minX: x - w / 2, minY, width: w, height: h };
}

/** Frame the place: its country with a margin, or a fixed span around the point. */
export function mapView(fence: MapFence, polygon: number[][] | null): MapView {
  const zoom = fence.zoom ?? (polygon ? "country" : "region");
  if (zoom === "world") return WORLD;
  const x = fence.lon;
  const y = -fence.lat;
  if (zoom === "country" && polygon) {
    const box = boxOf(polygon);
    const height = Math.max(
      (box.maxY - box.minY) * 1.6,
      ((box.maxX - box.minX) * 1.6) / MAP_ASPECT,
      MIN_COUNTRY_HEIGHT,
    );
    return centered((box.minX + box.maxX) / 2, (box.minY + box.maxY) / 2, height);
  }
  return centered(x, y, ZOOM_HEIGHT[zoom === "country" ? "region" : zoom]);
}

function overlaps(box: Box, view: MapView): boolean {
  return (
    box.maxX >= view.minX &&
    box.minX <= view.minX + view.width &&
    box.maxY >= view.minY &&
    box.minY <= view.minY + view.height
  );
}

/** SVG path data for one country, in map units. */
export function countryPath(country: MapCountry): string {
  return country.polygons
    .flat()
    .map((ring) => {
      let d = "";
      for (let i = 0; i < ring.length; i += 2) {
        d += `${i === 0 ? "M" : "L"}${ring[i] / 10} ${-ring[i + 1] / 10}`;
      }
      return `${d}Z`;
    })
    .join("");
}

/** Countries that show in the view; the rest are not drawn. */
export function countriesIn(view: MapView): MapCountry[] {
  return COUNTRIES.filter((country) => {
    const box = COUNTRY_BOXES.get(country.id + country.name);
    return box ? overlaps(box, view) : false;
  });
}

/** "0.02° N, 37.91° E" */
export function formatCoordinates(lat: number, lon: number): string {
  const ns = lat >= 0 ? "N" : "S";
  const ew = lon >= 0 ? "E" : "W";
  return `${Math.abs(lat).toFixed(2)}° ${ns}, ${Math.abs(lon).toFixed(2)}° ${ew}`;
}
