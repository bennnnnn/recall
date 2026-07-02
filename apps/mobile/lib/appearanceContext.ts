import { createContext } from "react";

import type { AppearancePreference } from "@/lib/appearance";

export type AppearanceContextValue = {
  preference: AppearancePreference;
  setPreference: (preference: AppearancePreference) => Promise<void>;
  colorScheme: "light" | "dark";
};

/** Standalone module so `useColorScheme` can read context without a circular import. */
export const AppearanceContext = createContext<AppearanceContextValue | null>(null);
