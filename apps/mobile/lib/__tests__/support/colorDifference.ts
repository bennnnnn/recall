/**
 * How different two colors look: CIEDE2000 (ΔE00) between two #RRGGBB colors.
 * About 1 is the smallest difference a reader notices; above 10 two colors
 * read as different colors at a glance.
 */

type Lab = [number, number, number];

const rad = (deg: number) => (deg * Math.PI) / 180;
const deg = (r: number) => (r * 180) / Math.PI;

function toLab(hex: string): Lab {
  const n = parseInt(hex.replace("#", ""), 16);
  const [r, g, b] = [n >> 16, (n >> 8) & 0xff, n & 0xff].map((c) => {
    const s = c / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  // sRGB → XYZ (D65), relative to the white point.
  const x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047;
  const y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  const z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883;
  const f = (t: number) => (t > 216 / 24389 ? Math.cbrt(t) : (24389 / 27 * t + 16) / 116);
  return [116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))];
}

/** Hue angle in degrees, 0–360. */
function hue(a: number, b: number): number {
  return a === 0 && b === 0 ? 0 : (deg(Math.atan2(b, a)) + 360) % 360;
}

export function colorDifference(hexA: string, hexB: string): number {
  const [l1, a1, b1] = toLab(hexA);
  const [l2, a2, b2] = toLab(hexB);
  const cMean = (Math.hypot(a1, b1) + Math.hypot(a2, b2)) / 2;
  const g = 0.5 * (1 - Math.sqrt(cMean ** 7 / (cMean ** 7 + 25 ** 7)));
  const c1 = Math.hypot((1 + g) * a1, b1);
  const c2 = Math.hypot((1 + g) * a2, b2);
  const h1 = hue((1 + g) * a1, b1);
  const h2 = hue((1 + g) * a2, b2);

  let dh = c1 * c2 === 0 ? 0 : h2 - h1;
  if (dh > 180) dh -= 360;
  else if (dh < -180) dh += 360;
  const dL = l2 - l1;
  const dC = c2 - c1;
  const dH = 2 * Math.sqrt(c1 * c2) * Math.sin(rad(dh / 2));

  const lMean = (l1 + l2) / 2;
  const cpMean = (c1 + c2) / 2;
  let hMean = h1 + h2;
  if (c1 * c2 !== 0) hMean = Math.abs(h1 - h2) <= 180 ? hMean / 2 : (hMean + (hMean < 360 ? 360 : -360)) / 2;
  const t =
    1 -
    0.17 * Math.cos(rad(hMean - 30)) +
    0.24 * Math.cos(rad(2 * hMean)) +
    0.32 * Math.cos(rad(3 * hMean + 6)) -
    0.2 * Math.cos(rad(4 * hMean - 63));
  const sl = 1 + (0.015 * (lMean - 50) ** 2) / Math.sqrt(20 + (lMean - 50) ** 2);
  const sc = 1 + 0.045 * cpMean;
  const sh = 1 + 0.015 * cpMean * t;
  const rc = 2 * Math.sqrt(cpMean ** 7 / (cpMean ** 7 + 25 ** 7));
  const rt = -Math.sin(rad(60 * Math.exp(-(((hMean - 275) / 25) ** 2)))) * rc;
  return Math.sqrt((dL / sl) ** 2 + (dC / sc) ** 2 + (dH / sh) ** 2 + rt * (dC / sc) * (dH / sh));
}
