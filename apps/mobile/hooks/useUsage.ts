import { useCallback, useEffect, useState } from "react";
import { AppState } from "react-native";
import { useFocusEffect } from "expo-router";

import { useAuthToken } from "@/contexts/AuthContext";
import { api, type Usage } from "@/lib/api";

export function useUsage() {
  const token = useAuthToken();
  const [usage, setUsage] = useState<Usage | null>(null);

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      setUsage(await api.todayUsage(token));
    } catch {
      // Keep the last successful read; defaults still render the window.
    }
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      void refresh();
    }, [refresh]),
  );

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") void refresh();
    });
    return () => subscription.remove();
  }, [refresh]);

  return usage;
}
