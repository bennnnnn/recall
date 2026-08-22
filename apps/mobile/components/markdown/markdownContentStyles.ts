import { StyleSheet } from "react-native";

import { CODE_FONT } from "@/lib/fonts";
import type { Theme } from "@/lib/theme";
import { Type } from "@/lib/type";

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
      marginLeft: 8,
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
    // Filled disc (ChatGPT-style). iOS used to render U+00B7 middle-dot,
    // which is a hairline glyph at body size and reads as "no bullet".
    listBullet: {
      width: 7,
      height: 7,
      borderRadius: 4,
      backgroundColor: t.primary,
      // Body is 16/22 — center the disc on the first line.
      marginTop: 8,
      marginRight: 10,
      marginLeft: 2,
      flexShrink: 0,
    },
  });
}

export function makeMdTable(t: Theme) {
  return StyleSheet.create({
    cellText: { fontSize: 15, lineHeight: 22, color: t.text, flexShrink: 1 },
    headerText: { fontWeight: "600", color: t.text },
    cellCode: {
      backgroundColor: t.contentSurface,
      color: t.text,
      fontFamily: CODE_FONT,
      fontSize: 13,
      lineHeight: 18,
      paddingHorizontal: 3,
      paddingVertical: 0,
      borderRadius: 3,
    },
  });
}

export function makeMdImg(t: Theme) {
  return StyleSheet.create({
    image: {
      width: "100%",
      height: 200,
      borderRadius: 8,
      marginVertical: 6,
      backgroundColor: t.contentSurface,
    },
  });
}

export function makeMdStyles(t: Theme) {
  return StyleSheet.create({
    body: { ...Type.body, color: t.assistantText },
    code_inline: {
      backgroundColor: t.contentSurface,
      color: t.text,
      borderRadius: 4,
      paddingHorizontal: 4,
      fontFamily: CODE_FONT,
      fontSize: 14,
      lineHeight: 20,
    },
    // Custom fence renderer handles code blocks / HTML preview inline.
    fence: { marginVertical: 0, padding: 0 },
    paragraph: { marginVertical: 0 },
    // Text-only paragraph run. Do not reuse `paragraph` — markdown-display
    // mergeStyle copies flexDirection/flexWrap/width onto that key.
    paragraphRun: { marginTop: 0, marginBottom: 10 },
    bullet_list: { marginVertical: 8 },
    ordered_list: { marginVertical: 8 },
    heading1: { ...Type.h1, marginTop: 18, marginBottom: 8, color: t.text },
    heading2: { ...Type.h2, marginTop: 16, marginBottom: 6, color: t.text },
    heading3: { ...Type.h3, marginTop: 12, marginBottom: 4, color: t.text },
    heading4: { ...Type.h4, marginTop: 10, marginBottom: 4, color: t.text },
    heading5: { ...Type.h5, marginTop: 8, marginBottom: 2, color: t.text },
    heading6: { ...Type.h6, marginTop: 8, marginBottom: 2, color: t.text },
    strong: { fontWeight: "700", color: t.text },
    em: { fontStyle: "italic" },
    blockquote: { marginVertical: 0, padding: 0, borderWidth: 0 },
    hr: { backgroundColor: t.border, height: 1, marginVertical: 12 },
    link: { color: t.primary },
  });
}

export type MdTableStyles = ReturnType<typeof makeMdTable>;
export type MdMathStyles = ReturnType<typeof makeMdMath>;
export type MdImgStyles = ReturnType<typeof makeMdImg>;
