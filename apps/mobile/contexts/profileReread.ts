/**
 * Reading the signed-in user again (`contexts/useProfileReread.ts`), for a screen to ask for:
 * a Settings page that gains focus calls it with SETTINGS_PROFILE_STALE_MS. `AuthProvider`
 * provides it; no imports, so a screen reads it without the sign-in stack, and outside a
 * provider (a screen test) it reads nothing.
 */

import { createContext, useContext } from "react";

/** How old the profile may be when a Settings page gains focus before it is read again. */
export const SETTINGS_PROFILE_STALE_MS = 30_000;

/** Reads `/auth/me` again unless the profile (or a try at it) is younger than `maxAgeMs`. */
export type RereadProfile = (maxAgeMs: number) => void;

export const ProfileRereadContext = createContext<RereadProfile>(() => {});

export function useRereadProfile(): RereadProfile {
  return useContext(ProfileRereadContext);
}
