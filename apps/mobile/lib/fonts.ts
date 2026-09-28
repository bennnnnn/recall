/** SpaceMono from @expo-google-fonts/space-mono. Registered in _layout without blocking first paint. */
export const CODE_FONT = "SpaceMono";

export { UI_FONT, uiFontFamily } from "@/lib/uiFont";

/**
 * KaTeX's Computer Modern faces are purpose-built for mathematical notation.
 * Main carries digits/operators; Math Italic gives variables an unmistakable
 * lowercase silhouette (notably x in large final answers).
 */
export const MATH_FONT = "KaTeX_Main";
export const MATH_VARIABLE_FONT = "KaTeX_MathItalic";
/**
 * AMS relations that KaTeX_Main does not carry (`∴`, `∵`) and the
 * double-struck capitals KaTeX draws from this face. Most relations (`≤`,
 * `∈`, `∞`) are in KaTeX_Main and must stay there.
 */
export const MATH_SYMBOL_FONT = "KaTeX_AMS";
