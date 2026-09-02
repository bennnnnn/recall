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

import { useAuthOptional } from "@/contexts/AuthContext";
import { api, type Project } from "@/lib/api";
import { StaleResourceCache } from "@/lib/cache/staleResource";
import { CONTEXT_REFRESH_STALE_MS } from "@/lib/cache/contextRefresh";

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
  const resourceRef = useRef(
    new StaleResourceCache<string, Project[]>(CONTEXT_REFRESH_STALE_MS),
  );
  const projectsRef = useRef(projects);
  projectsRef.current = projects;

  const refresh = useCallback(
    async (opts?: { silent?: boolean; force?: boolean }) => {
      if (!token) {
        setProjects([]);
        setLoading(false);
        setError(false);
        resourceRef.current.clear();
        return;
      }
      if (
        !opts?.force &&
        projectsRef.current.length > 0 &&
        resourceRef.current.isFresh(token)
      ) {
        return;
      }
      if (!opts?.silent) {
        setLoading(true);
      }
      setError(false);

      try {
        const data = await resourceRef.current.fetch(
          token,
          () => api.listProjects(token),
          { force: opts?.force || projectsRef.current.length === 0 },
        );
        setProjects(data);
      } catch {
        setError(true);
      } finally {
        if (!opts?.silent) setLoading(false);
      }
    },
    [token],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Focus refresh lives on Learning screens — do not refetch from this
  // app-wide provider on every route change.
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
