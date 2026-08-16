/** Left-edge hit slop for swipe-to-open (pt). */
export const DRAWER_EDGE_WIDTH = 28;
/** Ignore jitter until the finger has clearly moved. */
export const DRAWER_PAN_SLOP = 10;

/**
 * Whether the shell pan should claim this move.
 * Closed: only a rightward swipe from the left edge.
 * Open: drag the panel itself, or swipe the scrim left to close.
 */
export function shouldClaimDrawerPan(opts: {
  open: boolean;
  startX: number;
  dx: number;
  dy: number;
  drawerWidth: number;
  edgeWidth?: number;
  slop?: number;
}): boolean {
  const edgeWidth = opts.edgeWidth ?? DRAWER_EDGE_WIDTH;
  const slop = opts.slop ?? DRAWER_PAN_SLOP;
  const { open, startX, dx, dy, drawerWidth } = opts;
  if (Math.abs(dx) < slop && Math.abs(dy) < slop) return false;
  if (Math.abs(dy) >= Math.abs(dx)) return false;
  if (!open) return startX <= edgeWidth && dx > 0;
  if (startX >= drawerWidth) return dx < 0;
  return true;
}
