/**
 * Height policy for the chart WebView preview.
 * Grow-only after first paint so the assistant bubble does not jump.
 */
export const CHART_MIN_HEIGHT = 140;
/** Fit a 6-row horizontal bar chart plus title/axes. */
export const CHART_MAX_HEIGHT = 480;
export const CHART_MAX_EXPANDED = 800;
export const CHART_HEIGHT_EPSILON_PX = 4;
/** Placeholder until the SVG reports its size. */
export const CHART_PREVIEW_HEIGHT = CHART_MIN_HEIGHT;

export function clampChartPreviewHeight(reported: number, maxHeight: number): number {
  if (!Number.isFinite(reported) || reported <= 0) return CHART_MIN_HEIGHT;
  return Math.min(maxHeight, Math.max(CHART_MIN_HEIGHT, Math.ceil(reported)));
}

export function nextChartPreviewHeight(
  reported: number,
  current: number,
  maxHeight: number,
): number | null {
  const next = clampChartPreviewHeight(reported, maxHeight);
  if (next <= current + CHART_HEIGHT_EPSILON_PX) return null;
  return next;
}
