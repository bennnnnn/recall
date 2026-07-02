import { useContext } from "react";
import { useColorScheme as useSystemColorScheme } from "react-native";

import { AppearanceContext } from "@/contexts/AppearanceContext";
import { resolveColorScheme } from "@/lib/appearance";

export const useColorScheme = (): "light" | "dark" => {
  const ctx = useContext(AppearanceContext);
  const systemScheme = useSystemColorScheme();

  if (ctx) {
    return ctx.colorScheme;
  }

  return resolveColorScheme(systemScheme, "system");
};
