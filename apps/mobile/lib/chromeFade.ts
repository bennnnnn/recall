import type { Theme } from "@/lib/theme";

/** Extra height below chrome so list content fades out gradually (matches drawer). */
export const CHROME_FADE_EXTRA = 40;

export const TOP_CHROME_FADE_LOCATIONS = [0, 0.25, 0.5, 0.78, 1] as const;
export const BOTTOM_CHROME_FADE_LOCATIONS = [0, 0.35, 0.72, 1] as const;

export function topChromeFadeColors(theme: Theme): readonly string[] {
  if (theme.isDark) {
    return [theme.bg, `${theme.bg}FA`, `${theme.bg}D0`, `${theme.bg}70`, `${theme.bg}00`];
  }
  return [
    theme.bg,
    "rgba(255,255,255,0.98)",
    "rgba(255,255,255,0.82)",
    "rgba(255,255,255,0.45)",
    "rgba(255,255,255,0)",
  ];
}

export function bottomChromeFadeColors(theme: Theme): readonly string[] {
  if (theme.isDark) {
    return [`${theme.bg}00`, `${theme.bg}70`, `${theme.bg}D0`, theme.bg];
  }
  return [
    "rgba(255,255,255,0)",
    "rgba(255,255,255,0.45)",
    "rgba(255,255,255,0.82)",
    "rgba(255,255,255,0.95)",
  ];
}
