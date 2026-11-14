/**
 * A drawing a screen reader cannot read inside (a web view's SVG): one image with a label
 * that says what it shows (GFX-02, 2026-11-13 STEM audit).
 */
export function imageLabelProps(label: string): {
  accessible: true;
  accessibilityRole: "image";
  accessibilityLabel: string;
} {
  return { accessible: true, accessibilityRole: "image", accessibilityLabel: label };
}
