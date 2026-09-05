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
import { AppState } from "react-native";
import { useAuthOptional } from "@/contexts/AuthContext";
import { api, type Project } from "@/lib/api";
import { getSessionGeneration, requireTokenSession } from "@/lib/auth";
import { isContextFresh } from "@/lib/cache/contextRefresh";

type Options = { silent?: boolean; force?: boolean; afterPending?: boolean };
type Update = (rows: Project[]) => Project[];
type Owner = {
  session: number;
  signedIn: boolean;
  rows: Project[];
  fetchedAt?: number;
  pending?: { task: Promise<void>; updates: Update[] };
};
type Value = {
  projects: Project[];
  loading: boolean;
  error: boolean;
  refresh: (opts?: Options) => Promise<void>;
  setProjects: Dispatch<SetStateAction<Project[]>>;
};
const ProjectsContext = createContext<Value | null>(null);
export function ProjectsProvider({ children }: { children: ReactNode }) {
  const auth = useAuthOptional();
  const token = useRef(auth?.token);
  token.current = auth?.token;
  const session = getSessionGeneration();
  const signedIn = Boolean(auth?.token);
  const owner = useMemo<Owner>(() => ({ session, signedIn, rows: [] }), [session, signedIn]);
  const current = useRef(owner);
  current.current = owner;
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const [state, setState] = useState({
    owner,
    projects: owner.rows,
    loading: signedIn,
    error: false,
  });
  const isCurrent = useCallback(
    () => mounted.current && current.current === owner && owner.session === getSessionGeneration(),
    [owner],
  );
  const publish = useCallback(
    (patch: Partial<Value> = {}) => {
      if (isCurrent())
        setState((prev) => ({
          ...(prev.owner === owner ? prev : { loading: owner.signedIn, error: false }),
          owner,
          projects: owner.rows,
          ...patch,
        }));
    },
    [owner, isCurrent],
  );
  const setProjects = useCallback<Dispatch<SetStateAction<Project[]>>>(
    (action) => {
      if (!isCurrent() || !owner.signedIn) return;
      const update: Update = typeof action === "function" ? action : () => action;
      current.current.rows = update(owner.rows);
      owner.pending?.updates.push(update);
      publish();
    },
    [isCurrent, owner, publish],
  );
  const refresh = useCallback(
    async (opts?: Options) => {
      if (!token.current || !owner.signedIn || !isCurrent()) return;
      if (opts?.afterPending && owner.pending) {
        await owner.pending.task;
        if (!isCurrent()) return;
        current.current.fetchedAt = undefined;
      }
      if (owner.pending) return owner.pending.task;
      if (!opts?.force && !opts?.afterPending && isContextFresh(owner.fetchedAt)) return;
      const requestToken = token.current;
      const updates: Update[] = [];
      publish({ loading: !opts?.silent && owner.rows.length === 0, error: false });
      const task = (async () => {
        try {
          requireTokenSession(requestToken);
          const rows = await api.listProjects(requestToken);
          if (!isCurrent()) return;
          current.current.rows = updates.reduce((value, update) => update(value), rows);
          current.current.fetchedAt = Date.now();
          publish({ loading: false, error: false });
        } catch {
          publish({ loading: false, error: true });
        }
      })();
      const pending = { task, updates };
      current.current.pending = pending;
      try {
        await task;
      } finally {
        if (current.current === owner && owner.pending === pending)
          current.current.pending = undefined;
      }
    },
    [owner, isCurrent, publish],
  );
  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") void refresh({ silent: true });
    });
    return () => subscription.remove();
  }, [refresh]);
  const value = useMemo(
    () => ({
      ...(state.owner === owner
        ? state
        : { projects: owner.rows, loading: signedIn, error: false }),
      refresh,
      setProjects,
    }),
    [state, owner, signedIn, refresh, setProjects],
  );
  return <ProjectsContext.Provider value={value}>{children}</ProjectsContext.Provider>;
}
export function useProjects() {
  const context = useContext(ProjectsContext);
  if (!context) throw new Error("useProjects must be used within ProjectsProvider");
  return context;
}
