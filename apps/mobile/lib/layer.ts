/**
 * Overlay stacking for chrome (headers, composer, drawer, toasts).
 * Chart/illustration internals may keep local z-index.
 */
export const Layer = {
  /** Behind the main column (drawer open). */
  base: 0,
  /** Main column / in-flow raised bits. */
  content: 1,
  /** In-screen overlays (scanner mask, inline FABs). */
  overlay: 10,
  fab: 20,
  header: 100,
  composer: 110,
  drawer: 200,
  /** Banners and transient toasts above everything in-tree. */
  toast: 9999,
} as const;
