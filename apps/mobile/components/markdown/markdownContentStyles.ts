import { StyleSheet } from "react-native";

import { CODE_FONT } from "@/lib/fonts";
import type { Theme } from "@/lib/theme";

/** ChatGPT-style green verification tick for checked `- [x]` list items. */
export const VERIFY_CHECK_COLOR = "#10A37F";

export const verifyCheckStyles = StyleSheet.create({
  badge: {
    width: 20,
    height: 20,
    borderRadius: 4,
    backgroundColor: VERIFY_CHECK_COLOR,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: 8,
    marginTop: 2,
    flexShrink: 0,
  },
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

export function makeMdMath(_t: Theme) {
  return StyleSheet.create({
    listContent: {
      flex: 1,
      flexShrink: 1,
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
    body: { color: t.assistantText, fontSize: 16, lineHeight: 25 },
    code_inline: {
      backgroundColor: t.contentSurface,
      color: t.text,
      borderRadius: 4,
      paddingHorizontal: 4,
      fontFamily: CODE_FONT,
      fontSize: 14,
    },
    // Custom fence renderer handles code blocks / HTML preview inline.
    fence: { marginVertical: 0, padding: 0 },
    paragraph: { marginVertical: 0 },
    bullet_list: { marginVertical: 4 },
    ordered_list: { marginVertical: 4 },
    heading1: { fontSize: 20, fontWeight: "700", marginBottom: 8, color: t.text },
    heading2: { fontSize: 18, fontWeight: "700", marginBottom: 6, color: t.text },
    heading3: { fontSize: 16, fontWeight: "600", marginBottom: 4, color: t.text },
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
