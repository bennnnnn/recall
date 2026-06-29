import type { Theme } from "@/lib/theme";

/** Shared stack header options — keeps back chevron and title styling consistent. */
export function stackHeaderOptions(theme: Theme) {
  return {
    headerStyle: { backgroundColor: theme.bg },
    headerTitleStyle: {
      fontWeight: "700" as const,
      fontSize: 17,
      color: theme.text,
    },
    headerShadowVisible: false,
    headerTintColor: theme.primary,
    headerBackTitle: "",
    headerBackTitleVisible: false,
  } as const;
}
