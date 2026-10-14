#!/usr/bin/env node
/**
 * Builds lib/map/worldCountries.generated.json — country outlines for the
 * ```map card — from world-atlas (Natural Earth 1:110m, public domain) via
 * topojson-client, both dev dependencies.
 *
 *   pnpm world-map
 *
 * Each country keeps its numeric id, its name and its rings as flat
 * [lon, lat, lon, lat, …] lists in tenths of a degree (integers keep the file
 * small; 1:110m outlines are coarser than that anyway).
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { feature } from "topojson-client";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const topology = JSON.parse(
  readFileSync(join(root, "node_modules", "world-atlas", "countries-110m.json"), "utf8"),
);
const { features } = feature(topology, topology.objects.countries);

function ring(points) {
  const flat = [];
  let lastLon = null;
  let lastLat = null;
  // A ring that crosses the 180° line (Russia, Fiji) is unwrapped past it, so
  // it draws as one shape instead of a streak across the map.
  let shift = 0;
  let previous = null;
  for (const [rawLon, lat] of points) {
    if (previous !== null && Math.abs(rawLon + shift - previous) > 180) {
      shift += rawLon + shift > previous ? -360 : 360;
    }
    const lon = rawLon + shift;
    previous = lon;
    const x = Math.round(lon * 10);
    const y = Math.round(lat * 10);
    if (x === lastLon && y === lastLat) continue;
    flat.push(x, y);
    lastLon = x;
    lastLat = y;
  }
  return flat;
}

function polygons(geometry) {
  if (!geometry) return [];
  if (geometry.type === "Polygon") return [geometry.coordinates];
  if (geometry.type === "MultiPolygon") return geometry.coordinates;
  return [];
}

const countries = features
  .map((item) => ({
    id: String(item.id ?? ""),
    name: item.properties?.name ?? "",
    // Outer ring first in each polygon; holes follow and are drawn even-odd.
    polygons: polygons(item.geometry).map((rings) => rings.map(ring).filter((r) => r.length >= 6)),
  }))
  // Antarctica circles the pole and is cropped off every map view.
  .filter((country) => country.name && country.name !== "Antarctica" && country.polygons.length)
  .sort((a, b) => a.name.localeCompare(b.name));

writeFileSync(
  join(root, "lib", "map", "worldCountries.generated.json"),
  `${JSON.stringify(countries)}\n`,
);
const points = countries.reduce(
  (sum, c) => sum + c.polygons.flat().reduce((n, r) => n + r.length / 2, 0),
  0,
);
console.log(`Wrote ${countries.length} countries, ${points} points.`);
