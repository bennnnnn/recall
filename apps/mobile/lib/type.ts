/**
 * Shared type roles — prefer these over one-off 13/14/15/16 mixes for the
 * same visual job. Colors stay on theme tokens; this file owns size/weight.
 *
 * Dynamic Type: roles keep the platform default (`allowFontScaling`), so
 * body copy follows the reader. Math layout has its own scale. A control
 * that shares a line with a 44pt target (the composer field) sets
 * `maxFontSizeMultiplier` to `DYNAMIC_TYPE_MAX` so a very large size does
 * not clip the caret or the send button. Digits in a fixed box (the pickers)
 * stop sooner, at `DYNAMIC_TYPE_PICKER_MAX`.
 */
import type { TextStyle } from "react-native";

import { UI_FONT_FAMILY } from "@/lib/uiFont";

/** Cap for a control that shares a line with a 44pt target. Body copy stays uncapped. */
export const DYNAMIC_TYPE_MAX = 1.5;

/**
 * Cap for digits in a fixed box: the time picker's readout, the clock dial's
 * numbers, the calendar's days and years. Their boxes are sized for this.
 */
export const DYNAMIC_TYPE_PICKER_MAX = 1.3;

function face(weight: "400" | "500" | "600" | "700"): Pick<TextStyle, "fontFamily" | "fontWeight"> {
  return { fontFamily: UI_FONT_FAMILY, fontWeight: weight };
}

export const Type = {
  /** Primary body copy: iOS Body, 17pt.
   *
   *  Every role sets its line height: the system face's own line (1.19 em) packs prose
   *  tight, so each role keeps about the air Source Sans gave (1.42 em). React Native
   *  scales it with the reader's text size. A paragraph with tall maths lays out words
   *  and formulas as items in a wrapping row, so its lines still grow to the formula. */
  body: {
    fontSize: 17,
    lineHeight: 24,
    ...face("400"),
  },
  /** Chat replies and messages: a size up from the body with reading air, 18 on 28
   *  (1.55 em), as ChatGPT sets its answers. The rest of the UI keeps the body. */
  reading: {
    fontSize: 18,
    lineHeight: 28,
    ...face("400"),
  },
  /** Secondary body / supporting paragraphs */
  secondary: {
    fontSize: 15,
    lineHeight: 21,
    ...face("400"),
  },
  /** Captions / compact meta */
  caption: {
    fontSize: 12,
    lineHeight: 16,
    ...face("500"),
  },
  /** 12pt regular meta — timestamps, domain lines, "PDF" kind labels. */
  meta: {
    fontSize: 12,
    lineHeight: 16,
    ...face("400"),
  },
  /** 11pt uppercase tracked overline — drawer/home section dividers. */
  overline: {
    fontSize: 11,
    lineHeight: 15,
    ...face("700"),
    textTransform: "uppercase",
    letterSpacing: 0.8,
  },
  /** 11pt bold, untracked — counts and tags inside a badge. The overline's
   *  size without its uppercase tracking. */
  micro: {
    fontSize: 11,
    lineHeight: 14,
    ...face("700"),
  },
  /** 13pt compact chrome — banners, inline alerts, supporting meta that
   *  sat between caption (12) and secondary (15). Override weight at the site. */
  compact: {
    fontSize: 13,
    lineHeight: 18,
    ...face("400"),
  },
  /** Compact control labels */
  label: {
    fontSize: 15,
    lineHeight: 20,
    ...face("600"),
  },
  /** 16pt callout — toasts and dense card titles between body (17) and
   *  secondary (15). */
  callout: {
    fontSize: 16,
    lineHeight: 22,
    ...face("600"),
  },
  /** Screen / section titles */
  title: {
    fontSize: 20,
    lineHeight: 26,
    ...face("600"),
  },
  /** Nav bar & sheet titles — the 17pt role the scale was missing (8+ sites
   *  invented it as `...Type.title, fontSize: 17` or a bare 17/700). */
  navTitle: {
    fontSize: 17,
    lineHeight: 22,
    ...face("600"),
  },
  /** Onboarding / marketing display. Tightened: 28pt bold reads loose at 0. */
  display: {
    fontSize: 28,
    lineHeight: 34,
    ...face("700"),
    letterSpacing: -0.5,
  },
  /** Large clock numerals (time picker header). Tabular so digits don't jiggle. */
  clock: {
    fontSize: 56,
    ...face("400"),
    fontVariant: ["tabular-nums"],
  },
  /** Markdown heading ladder (h1–h6). Wrapped headings keep scaled line boxes. */
  h1: { fontSize: 26, lineHeight: 32, ...face("700") },
  h2: { fontSize: 22, lineHeight: 28, ...face("700") },
  h3: { fontSize: 20, lineHeight: 26, ...face("700") },
  /** Section label — never smaller than the reading size, or hierarchy inverts. */
  h4: { fontSize: 18, lineHeight: 26, ...face("700") },
  h5: { fontSize: 18, lineHeight: 26, ...face("700") },
  h6: { fontSize: 18, lineHeight: 26, ...face("700") },
} as const satisfies Record<string, TextStyle>;

/**
 * Weight changes on top of a role: `{ ...Type.body, ...Weight.bold }`. The
 * system face carries every weight, so each entry is the family and its
 * weight together. Lint bans raw `fontWeight`; use this instead.
 */
export const Weight = {
  regular: face("400"),
  medium: face("500"),
  semibold: face("600"),
  bold: face("700"),
} as const satisfies Record<string, TextStyle>;

/**
 * Italic on top of a role: `{ ...Type.body, ...Italic.regular }`. The system
 * face has true italics at every weight.
 */
export const Italic = {
  regular: { ...face("400"), fontStyle: "italic" },
  semibold: { ...face("600"), fontStyle: "italic" },
  bold: { ...face("700"), fontStyle: "italic" },
} as const satisfies Record<string, TextStyle>;
