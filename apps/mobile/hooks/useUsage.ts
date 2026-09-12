import { useCallback, useEffect, useRef, useState } from "react";
import { AppState } from "react-native";
import { useFocusEffect } from "expo-router";

import { useAuthToken } from "@/contexts/AuthContext";
import type { Usage } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import {
  fetchTodayUsage,
  getCachedUsage,
  invalidateUsageCache,
} from "@/lib/cache/usageCache";

type UsageState = {
  token: string | null;
  generation: number;
  usage: Usage | null;
  loading: boolean;
  error: boolean;
};

function todayUsage(usage: Usage | null | undefined): Usage | null {
  return usage?.date === new Date().toISOString().slice(0, 10) ? usage : null;
}

export function useUsage() {
  const token = useAuthToken();
  const generation = getSessionGeneration();
  const tokenRef = useRef(token);
  tokenRef.current = token;
  const mountedRef = useRef(false);
  const requestRef = useRef(0);
  const [state, setState] = useState<UsageState>(() => ({
    token,
    generation,
    usage: token ? todayUsage(getCachedUsage(token)) : null,
    loading: Boolean(token),
    error: false,
  }));

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestRef.current += 1;
    };
  }, []);

  const refresh = useCallback(async (opts?: { force?: boolean }) => {
    const isCurrent = () =>
      mountedRef.current && tokenRef.current === token && generation === getSessionGeneration();
    if (!token || !isCurrent()) return;
    const request = ++requestRef.current;
    const cached = getCachedUsage(token);
    setState((previous) => ({
      token,
      generation,
      usage: previous.token === token && previous.generation === generation
        ? todayUsage(previous.usage)
        : todayUsage(cached),
      loading: true,
      error: false,
    }));
    const data = await fetchTodayUsage(token, {
      force: opts?.force || Boolean(cached && !todayUsage(cached)),
    });
    if (!isCurrent() || request !== requestRef.current) return;
    const currentUsage = todayUsage(data);
    setState({ token, generation, usage: currentUsage, loading: false, error: !currentUsage });
  }, [token, generation]);

  useFocusEffect(
    useCallback(() => {
      void refresh();
    }, [refresh]),
  );

  useEffect(() => {
    if (!token) {
      invalidateUsageCache();
      return;
    }
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") void refresh();
    });
    return () => subscription.remove();
  }, [refresh, token]);

  const isCurrentState = state.token === token && state.generation === generation;
  return {
    usage: isCurrentState ? todayUsage(state.usage) : null,
    loading: isCurrentState ? state.loading : Boolean(token),
    error: isCurrentState && state.error,
    refresh,
  };
}
