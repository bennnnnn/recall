import { useCallback, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";
import { getSessionGeneration } from "@/lib/auth";
import { useAuth } from "@/contexts/AuthContext";

type ViewOwner = { session: number; visit: number; signedIn: boolean };

/**
 * Dialogs and screen callbacks belong to one focused account visit. `key` names the account
 * only: another sign-in remounts the screen, a blur and return does not (a visit in the key
 * remounted Memory, To-do and Notifications on every return: the scroll went back to the top,
 * the page flickered and read twice). `isCurrent` still ends with the visit, so an answer that
 * lands after a blur changes nothing on the page.
 */
export function useAccountViewOwner() {
  // Subscribe here: context changes can rerender a child without its wrapper.
  const { token } = useAuth();
  const signedIn = Boolean(token);
  const session = getSessionGeneration();
  const visit = useRef(0);
  const active = useRef<ViewOwner | null>(null);
  const [owner, setOwner] = useState<ViewOwner | null>(null);
  useFocusEffect(useCallback(() => {
    const next = { session, signedIn, visit: ++visit.current };
    active.current = next;
    setOwner(next);
    return () => {
      if (active.current === next) {
        active.current = null;
        setOwner(null);
      }
    };
  }, [session, signedIn]));
  const isCurrent = useCallback(() => owner !== null && owner.signedIn && active.current === owner &&
    owner.session === getSessionGeneration(), [owner]);
  return { key: `${session}:${signedIn}`, isCurrent };
}
