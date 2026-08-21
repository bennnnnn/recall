import { useCallback, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";

import { useAuthToken } from "@/contexts/AuthContext";
import { useHome } from "@/contexts/HomeContext";
import type { ProjectDetail } from "@/lib/api";
import {
  fetchProjectDetail,
  getCachedProjectDetail,
  isProjectDetailFresh,
} from "@/lib/cache/projectDetailCache";

export function useProjectDetail(projectId: string | undefined) {
  const token = useAuthToken();
  const { refresh: refreshHome } = useHome();
  const initial = projectId ? getCachedProjectDetail(projectId) ?? null : null;
  const [project, setProject] = useState<ProjectDetail | null>(initial);
  const [loading, setLoading] = useState(!initial);
  const [loadError, setLoadError] = useState(false);
  const hasLoadedRef = useRef(Boolean(initial));
  const projectRef = useRef(project);
  projectRef.current = project;

  const load = useCallback(
    async (options?: { silent?: boolean; force?: boolean }) => {
      if (!token || !projectId) return;
      const firstLoad = !hasLoadedRef.current;
      if (!options?.silent && firstLoad && !projectRef.current) setLoading(true);
      setLoadError(false);
      const data = await fetchProjectDetail(token, projectId, { force: options?.force });
      if (data) {
        setProject(data);
      } else if (!projectRef.current) {
        setProject(null);
        setLoadError(true);
      }
      hasLoadedRef.current = true;
      if (!options?.silent && firstLoad) setLoading(false);
    },
    [projectId, token],
  );

  useFocusEffect(
    useCallback(() => {
      if (!projectId) return;
      const hasPaint = Boolean(projectRef.current || getCachedProjectDetail(projectId));
      void load({
        silent: hasPaint,
        force: !isProjectDetailFresh(projectId),
      });
      void refreshHome({ silent: true });
    }, [load, projectId, refreshHome]),
  );

  return { project, loading, loadError, load };
}
