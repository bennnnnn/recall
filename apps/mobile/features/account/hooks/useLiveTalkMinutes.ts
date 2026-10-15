import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";

import { useAuthToken } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

/** This month's live talk minutes left, refreshed whenever the screen is shown. */
export function useLiveTalkMinutes(enabled: boolean): { remaining: number; limit: number } | null {
  const token = useAuthToken();
  const [minutes, setMinutes] = useState<{ remaining: number; limit: number } | null>(null);

  useFocusEffect(
    useCallback(() => {
      if (!enabled || !token) {
        setMinutes(null);
        return;
      }
      let cancelled = false;
      void api
        .liveTalkStatus(token)
        .then((status) => {
          if (!cancelled && status.entitled) {
            setMinutes({ remaining: status.remaining, limit: status.limit });
          }
        })
        .catch(() => {
          // The row simply stays hidden; live talk itself re-checks on open.
        });
      return () => {
        cancelled = true;
      };
    }, [enabled, token]),
  );

  return minutes;
}
