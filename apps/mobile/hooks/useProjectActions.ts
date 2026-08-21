import { useCallback } from "react";

import { useAuthToken } from "@/contexts/AuthContext";
import { api, type LanguageLevel, type Project, type ProjectKind, type VocabStatus } from "@/lib/api";
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

  const requireToken = useCallback(() => {
    if (!token) throw new Error("Authentication required");
    return token;
  }, [token]);

  const createProject = useCallback(
    (input: CreateProjectInput) => api.createProject(requireToken(), input),
    [requireToken],
  );

  const updateProject = useCallback(
    async (projectId: string, patch: UpdateProjectInput) => {
      const updated = await api.updateProject(requireToken(), projectId, patch);
      invalidateProjectDetail(projectId);
      return updated;
    },
    [requireToken],
  );

  const updateProjectItem = useCallback(
    async (projectId: string, itemId: string, status: VocabStatus) => {
      const updated = await api.updateProjectItem(requireToken(), projectId, itemId, { status });
      invalidateProjectDetail(projectId);
      return updated;
    },
    [requireToken],
  );

  const deleteProject = useCallback(
    async (projectId: string) => {
      await api.deleteProject(requireToken(), projectId);
      invalidateProjectDetail(projectId);
    },
    [requireToken],
  );

  const getExportProject = useCallback(
    (projectId: string) => api.getProject(requireToken(), projectId, { includeLists: true }),
    [requireToken],
  );

  return { createProject, updateProject, updateProjectItem, deleteProject, getExportProject };
}
