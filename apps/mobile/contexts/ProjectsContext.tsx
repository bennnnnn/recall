import {
  createContext,
  useCallback,
  useContext,
  useEffect,
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

type ProjectsContextValue = {
  projects: Project[];
  loading: boolean;
  error: boolean;
  refresh: (opts?: { silent?: boolean }) => Promise<void>;
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
  projectsRef.current = projects;

  const refresh = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (!token) {
        setProjects([]);
        setLoading(false);
        setError(false);
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
      void refresh({ silent: projectsRef.current.length > 0 });
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

  const value: ProjectsContextValue = {
    projects,
    loading,
    error,
    refresh,
    setProjects,
  };

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
