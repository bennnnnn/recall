import { useCallback, useEffect, useState } from "react";
import { AppState } from "react-native";
import { useFocusEffect } from "expo-router";

import { useAuthToken } from "@/contexts/AuthContext";
import {
  fetchTodayUsage,
  getCachedUsage,
  invalidateUsageCache,
} from "@/lib/cache/usageCache";

export function useUsage() {
  const token = useAuthToken();
  const [usage, setUsage] = useState(() => (token ? (getCachedUsage(token) ?? null) : null));

  const refresh = useCallback(async () => {
    if (!token) {
      invalidateUsageCache();
      setUsage(null);
      return;
    }
    const data = await fetchTodayUsage(token);
    if (data) setUsage(data);
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      void refresh();
    }, [refresh]),
  );

  useEffect(() => {
    if (!token) {
      invalidateUsageCache();
      setUsage(null);
      return;
    }
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") void refresh();
    });
    return () => subscription.remove();
  }, [refresh, token]);

  return usage;
}
