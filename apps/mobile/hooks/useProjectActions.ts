import { useCallback } from "react";

import { useAuthToken } from "@/contexts/AuthContext";
import { api, type LanguageLevel, type Project, type ProjectKind } from "@/lib/api";
import { getSessionGeneration, requireTokenSession, SessionChangedError } from "@/lib/auth";
import { invalidateProjectDetail } from "@/lib/cache/projectDetailCache";

type CreateProjectInput = {
  title: string;
  description?: string | null;
  kind?: ProjectKind;
  target_language?: string;
  native_language?: string | null;
  level?: LanguageLevel;
  daily_goal?: number | null;
};

type UpdateProjectInput = Partial<
  Pick<
    Project,
    | "title"
    | "description"
    | "kind"
    | "archived"
    | "level"
    | "target_language"
    | "native_language"
    | "daily_goal"
  >
>;

export function useProjectActions() {
  const token = useAuthToken();
  const session = getSessionGeneration();
  const requireSession = useCallback(() => {
    if (session !== getSessionGeneration()) throw new SessionChangedError();
  }, [session]);

  const requireToken = useCallback(() => {
    if (!token) throw new Error("Authentication required");
    requireSession();
    requireTokenSession(token);
    return token;
  }, [token, requireSession]);

  const createProject = useCallback(
    async (input: CreateProjectInput) => {
      const created = await api.createProject(requireToken(), input);
      requireSession();
      return created;
    },
    [requireToken, requireSession],
  );

  const updateProject = useCallback(
    async (projectId: string, patch: UpdateProjectInput) => {
      const updated = await api.updateProject(requireToken(), projectId, patch);
      requireSession();
      invalidateProjectDetail(projectId, session);
      return updated;
    },
    [requireToken, requireSession, session],
  );

  const getExportProject = useCallback(
    async (projectId: string) => {
      const detail = await api.getProject(requireToken(), projectId, { includeLists: true });
      requireSession();
      return detail;
    },
    [requireToken, requireSession],
  );

  return { createProject, updateProject, getExportProject };
}
