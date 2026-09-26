import { StyleSheet, type TextStyle } from "react-native";

import { CODE_FONT } from "@/lib/fonts";
import type { Theme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";

/**
 * Nested-Text inline code. The markdown-display default is a block recipe
 * (`borderWidth: 1`, `padding: 10`); those props make iOS wrap each chip
 * onto its own line. Zero them here and keep the line box at body size.
 */
export function inlineCodeTextStyle(t: Theme): TextStyle {
  return {
    ...Type.secondary,
    fontFamily: CODE_FONT,
    color: t.text,
    backgroundColor: t.surfaceAlt,
    borderWidth: 0,
    borderColor: "transparent",
    padding: 0,
    paddingHorizontal: Space.xxs,
    paddingVertical: 0,
    borderRadius: 4,
  };
}

export const verifyCheckStyles = StyleSheet.create({
  verifyRow: {
    flex: 1,
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
  },
  verifyContent: {
    flex: 1,
    flexShrink: 1,
  },
});

/** Green verification tick badge for checked `- [x]` list items. */
export function makeVerifyCheckStyles(t: Theme) {
  return StyleSheet.create({
    badge: {
      width: 20,
      height: 20,
      borderRadius: 4,
      backgroundColor: t.success,
      alignItems: "center",
      justifyContent: "center",
      marginLeft: Space.xs,
      marginTop: 2,
      flexShrink: 0,
    },
  });
}

export function makeMdMath(t: Theme) {
  return StyleSheet.create({
    listContent: {
      flex: 1,
      flexShrink: 1,
    },
    // Hosts stacked frac/sqrt Views as siblings of Text — iOS lays out a
    // View nested inside Text as 0×0 and paints the numerator over the
    // previous line. Row+wrap keeps bold/prose inline without that clip.
    inlineWrap: {
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "center",
      alignSelf: "stretch",
    },
    // Filled disc (ChatGPT-style). iOS used to render U+00B7 middle-dot,
    // which is a hairline glyph at body size and reads as "no bullet".
    listBullet: {
      width: 7,
      height: 7,
      borderRadius: 4,
      backgroundColor: t.primary,
      // Body is 16/22 — center the disc on the first line.
      marginTop: Space.xs,
      marginRight: 10,
      marginLeft: 2,
      flexShrink: 0,
    },
  });
}

export function makeMdTable(t: Theme) {
  return StyleSheet.create({
    cellText: { ...Type.callout, ...Weight.regular, color: t.text, flexShrink: 1 },
    headerText: { ...Weight.semibold, color: t.text },
    cellCode: {
      ...inlineCodeTextStyle(t),
      ...Type.compact,
    },
  });
}

export function makeMdImg(t: Theme) {
  return StyleSheet.create({
    image: {
      width: "100%",
      height: 200,
      borderRadius: Radius.xs,
      marginVertical: 6,
      backgroundColor: t.contentSurface,
    },
  });
}

export function makeMdStyles(t: Theme) {
  return StyleSheet.create({
    body: { ...Type.body, color: t.assistantText },
    code_inline: inlineCodeTextStyle(t),
    // Custom fence renderer handles code blocks / HTML preview inline.
    fence: { marginVertical: 0, padding: 0 },
    paragraph: { marginVertical: 0 },
    // Text-only paragraph run. Do not reuse `paragraph` — markdown-display
    // mergeStyle copies flexDirection/flexWrap/width onto that key.
    paragraphRun: { marginTop: 0, marginBottom: 10 },
    bullet_list: { marginTop: 0, marginBottom: 10 },
    ordered_list: { marginTop: 0, marginBottom: 10 },
    list_item: { marginBottom: 6 },
    ordered_list_icon: {
      ...Type.body,
      color: t.textSecondary,
      minWidth: 22,
      textAlign: "right",
      marginLeft: 0,
      marginRight: Space.xs,
    },
    heading1: {
      ...Type.h1,
      marginTop: 18,
      marginBottom: Space.xs,
      color: t.text,
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "flex-start",
    },
    heading2: {
      ...Type.h2,
      marginTop: Space.md,
      marginBottom: 6,
      color: t.text,
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "flex-start",
    },
    heading3: {
      ...Type.h3,
      marginTop: Space.sm,
      marginBottom: Space.xxs,
      color: t.text,
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "flex-start",
    },
    heading4: {
      ...Type.h4,
      marginTop: 10,
      marginBottom: Space.xxs,
      color: t.text,
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "flex-start",
    },
    heading5: {
      ...Type.h5,
      marginTop: Space.xs,
      marginBottom: 2,
      color: t.text,
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "flex-start",
    },
    heading6: {
      ...Type.h6,
      marginTop: Space.xs,
      marginBottom: 2,
      color: t.text,
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "flex-start",
    },
    strong: { ...Weight.bold, color: t.text },
    em: { fontStyle: "italic" },
    blockquote: { marginVertical: 0, padding: 0, borderWidth: 0 },
    hr: { backgroundColor: t.border, height: 1, marginVertical: Space.sm },
    link: { color: t.primary },
  });
}

export type MdTableStyles = ReturnType<typeof makeMdTable>;
export type MdMathStyles = ReturnType<typeof makeMdMath>;
export type MdImgStyles = ReturnType<typeof makeMdImg>;
