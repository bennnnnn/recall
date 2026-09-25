/** Repeated chrome icon sizes. Prefer these over raw 20/22/24 on `Icon`.
 *  Domain graphics may keep other pixel sizes.
 *  Kept out of the glyph drawings so Node tests can import the scale. */
export const IconSize = {
  sm: 20,
  md: 22,
  lg: 24,
  hero: 28,
} as const;
