import { withAlpha, type Theme } from "@/lib/theme";

/** Extra height below chrome so list content fades out gradually (matches drawer). */
export const CHROME_FADE_EXTRA = 40;

export const TOP_CHROME_FADE_LOCATIONS = [0, 0.25, 0.5, 0.78, 1] as const;
export const BOTTOM_CHROME_FADE_LOCATIONS = [0, 0.35, 0.72, 1] as const;

// theme.bg is a solid hex in both palettes, so one alpha curve (via
// withAlpha) works identically for light and dark — no isDark branch needed.
export function topChromeFadeColors(theme: Theme): readonly string[] {
  return [
    theme.bg,
    withAlpha(theme.bg, 0.98),
    withAlpha(theme.bg, 0.82),
    withAlpha(theme.bg, 0.45),
    withAlpha(theme.bg, 0),
  ];
}

export function bottomChromeFadeColors(theme: Theme): readonly string[] {
  return [
    withAlpha(theme.bg, 0),
    withAlpha(theme.bg, 0.45),
    withAlpha(theme.bg, 0.82),
    theme.bg,
  ];
}
