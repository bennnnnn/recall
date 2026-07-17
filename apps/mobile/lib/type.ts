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
    lineHeight: 22,
  },
  /** Secondary body / supporting paragraphs */
  secondary: {
    fontSize: 15,
    fontWeight: "400",
    lineHeight: 22,
  },
  /** Uppercase section labels / meta captions */
  caption: {
    fontSize: 13,
    fontWeight: "600",
  },
  /** Compact control labels */
  label: {
    fontSize: 14,
    fontWeight: "600",
  },
} as const satisfies Record<string, TextStyle>;
