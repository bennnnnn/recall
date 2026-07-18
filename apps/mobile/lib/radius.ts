/**
 * Shared corner radii. Prefer these over one-off 10/12/14/16/999 mixes
 * for the same control role. Full app migration is incremental.
 */
export const Radius = {
  /** 8 — tight chips, compact controls */
  xs: 8,
  /** 10 — date chips, small panels */
  sm: 10,
  /** 12 — buttons, cards, code panels (default) */
  md: 12,
  /** 14 — soft pills, menu groups */
  lg: 14,
  /** 16 — large cards / settings groups */
  xl: 16,
  /** 20 — sheet top corners */
  sheet: 20,
  /** Pill / fully rounded */
  full: 999,
} as const;
