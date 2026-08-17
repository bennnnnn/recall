import type { Theme } from "@/lib/theme";
import { Type } from "@/lib/type";

/** Shared stack header options — keeps back chevron and title styling consistent. */
export function stackHeaderOptions(theme: Theme) {
  return {
    headerStyle: { backgroundColor: theme.bg },
    headerTitleStyle: {
      ...Type.navTitle,
      color: theme.text,
    },
    headerShadowVisible: false,
    headerTintColor: theme.text,
    headerBackTitle: "",
    headerBackTitleVisible: false,
  } as const;
}
