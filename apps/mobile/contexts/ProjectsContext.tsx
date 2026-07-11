import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";
import { AppState, type AppStateStatus } from "react-native";
import { useFocusEffect } from "expo-router";

import { useAuthOptional } from "@/contexts/AuthContext";
import { api, type Project } from "@/lib/api";
import { CONTEXT_REFRESH_STALE_MS } from "@/lib/contextRefresh";

type ProjectsContextValue = {
  projects: Project[];
  loading: boolean;
  error: boolean;
  refresh: (opts?: { silent?: boolean; force?: boolean }) => Promise<void>;
  setProjects: Dispatch<SetStateAction<Project[]>>;
};

const ProjectsContext = createContext<ProjectsContextValue | null>(null);

export function ProjectsProvider({ children }: { children: ReactNode }) {
  const auth = useAuthOptional();
  const token = auth?.token;
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const inflightRef = useRef<Promise<void> | null>(null);
  const projectsRef = useRef(projects);
  const lastFetchedRef = useRef(0);
  projectsRef.current = projects;

  const refresh = useCallback(
    async (opts?: { silent?: boolean; force?: boolean }) => {
      if (!token) {
        setProjects([]);
        setLoading(false);
        setError(false);
        lastFetchedRef.current = 0;
        return;
      }
      if (
        !opts?.force &&
        projectsRef.current.length > 0 &&
        Date.now() - lastFetchedRef.current < CONTEXT_REFRESH_STALE_MS
      ) {
        return;
      }
      if (inflightRef.current) {
        await inflightRef.current;
        return;
      }
      if (!opts?.silent) {
        setLoading(true);
      }
      setError(false);

      const task = (async () => {
        try {
          setProjects(await api.listProjects(token));
          lastFetchedRef.current = Date.now();
        } catch {
          setError(true);
        } finally {
          if (!opts?.silent) {
            setLoading(false);
          }
        }
      })();

      inflightRef.current = task;
      try {
        await task;
      } finally {
        inflightRef.current = null;
      }
    },
    [token],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useFocusEffect(
    useCallback(() => {
      void refresh({ silent: true });
    }, [refresh]),
  );

  useEffect(() => {
    if (!token) return;
    const onAppState = (state: AppStateStatus) => {
      if (state === "active") void refresh({ silent: true });
    };
    const sub = AppState.addEventListener("change", onAppState);
    return () => sub.remove();
  }, [refresh, token]);

  const value = useMemo<ProjectsContextValue>(
    () => ({
      projects,
      loading,
      error,
      refresh,
      setProjects,
    }),
    [projects, loading, error, refresh],
  );

  return (
    <ProjectsContext.Provider value={value}>{children}</ProjectsContext.Provider>
  );
}

export function useProjects() {
  const ctx = useContext(ProjectsContext);
  if (!ctx) {
    throw new Error("useProjects must be used within ProjectsProvider");
  }
  return ctx;
}

export function useProjectsOptional() {
  return useContext(ProjectsContext);
}
