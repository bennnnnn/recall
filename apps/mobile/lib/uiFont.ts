/** Source Sans 3, one file per weight. Loaded in the root layout. Not Inter. */
export const UI_FONT = {
  regular: "SourceSans3",
  medium: "SourceSans3-Medium",
  semibold: "SourceSans3-Semibold",
  bold: "SourceSans3-Bold",
} as const;

const UI_FONT_FOR_WEIGHT = {
  "400": UI_FONT.regular,
  "500": UI_FONT.medium,
  "600": UI_FONT.semibold,
  "700": UI_FONT.bold,
} as const;

export function uiFontFamily(weight: keyof typeof UI_FONT_FOR_WEIGHT): string {
  return UI_FONT_FOR_WEIGHT[weight];
}
