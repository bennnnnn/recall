/**
 * Shared type roles — prefer these over one-off 13/14/15/16 mixes for the
 * same visual job. Colors stay on theme tokens; this file owns size/weight.
 */
import type { TextStyle } from "react-native";

export const Type = {
  /** Primary body copy */
  body: {
    fontSize: 16,
    fontWeight: "400",
    lineHeight: 25,
  },
  /** Secondary body / supporting paragraphs */
  secondary: {
    fontSize: 14,
    fontWeight: "400",
    lineHeight: 20,
  },
  /** Captions / compact meta */
  caption: {
    fontSize: 12,
    fontWeight: "500",
  },
  /** 12pt regular meta — timestamps, domain lines, "PDF" kind labels.
   *  No lineHeight (matches caption/label: single-line roles omit it). */
  meta: {
    fontSize: 12,
    fontWeight: "400",
  },
  /** 11pt uppercase tracked overline — drawer/home section dividers.
   *  No lineHeight (single-line role). */
  overline: {
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.8,
  },
  /** Compact control labels */
  label: {
    fontSize: 14,
    fontWeight: "600",
  },
  /** Screen / section titles */
  title: {
    fontSize: 20,
    fontWeight: "600",
    lineHeight: 26,
  },
  /** Nav bar & sheet titles — the 17pt role the scale was missing (8+ sites
   *  invented it as `...Type.title, fontSize: 17` or a bare 17/700). */
  navTitle: {
    fontSize: 17,
    fontWeight: "600",
    lineHeight: 22,
  },
  /** Onboarding / marketing display */
  display: {
    fontSize: 28,
    fontWeight: "700",
    lineHeight: 34,
  },
  /** Markdown heading ladder (h1–h6). lineHeight prevents clipping when a
   *  heading wraps to two lines. */
  h1: { fontSize: 22, fontWeight: "700", lineHeight: 28 },
  h2: { fontSize: 19, fontWeight: "700", lineHeight: 26 },
  h3: { fontSize: 17, fontWeight: "700", lineHeight: 24 },
  /** Section label — never smaller than body, or hierarchy inverts. */
  h4: { fontSize: 16, fontWeight: "700", lineHeight: 22 },
  h5: { fontSize: 16, fontWeight: "700", lineHeight: 22 },
  h6: { fontSize: 16, fontWeight: "700", lineHeight: 22 },
} as const satisfies Record<string, TextStyle>;
