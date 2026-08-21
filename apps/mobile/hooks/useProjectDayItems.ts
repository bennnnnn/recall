import { useCallback, useEffect, useState } from "react";

import { useProjectActions } from "@/hooks/useProjectActions";
import { api, type ProjectItem } from "@/lib/api";

const PAGE_SIZE = 50;

type Options = {
  token: string;
  projectId: string;
  activityDate: string;
  itemsByDate?: Record<string, ProjectItem[]>;
  missedItems?: ProjectItem[];
  onItemUpdated?: () => void;
};

export function useProjectDayItems({
  token,
  projectId,
  activityDate,
  itemsByDate,
  missedItems: embeddedMisses,
  onItemUpdated,
}: Options) {
  const { updateProjectItem } = useProjectActions();
  const cachedItems = itemsByDate ? (itemsByDate[activityDate] ?? []) : undefined;
  const useEmbedded = itemsByDate !== undefined && embeddedMisses !== undefined;
  const [items, setItems] = useState<ProjectItem[]>(cachedItems ?? []);
  const [missedItems, setMissedItems] = useState<ProjectItem[]>(embeddedMisses ?? []);
  const [loading, setLoading] = useState(!useEmbedded && cachedItems === undefined);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);

  const fetchBucket = useCallback(
    (bucket: "mastered" | "missed") =>
      api.getProjectDailyItems(token, projectId, activityDate, {
        limit: PAGE_SIZE,
        offset: 0,
        bucket,
      }),
    [activityDate, projectId, token],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const [mastered, missed] = await Promise.all([
        fetchBucket("mastered"),
        fetchBucket("missed"),
      ]);
      setItems(mastered);
      setMissedItems(missed);
    } catch {
      setItems([]);
      setMissedItems([]);
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, [fetchBucket]);

  useEffect(() => {
    if (useEmbedded) {
      setItems(itemsByDate?.[activityDate] ?? []);
      setMissedItems(embeddedMisses ?? []);
      setLoading(false);
      setLoadError(false);
      return;
    }
    if (itemsByDate) {
      setItems(itemsByDate[activityDate] ?? []);
      setLoading(false);
      void fetchBucket("missed")
        .then(setMissedItems)
        .catch(() => setMissedItems([]));
      return;
    }
    void load();
  }, [activityDate, embeddedMisses, fetchBucket, itemsByDate, load, useEmbedded]);

  const changeStatus = useCallback(
    async (itemId: string, status: "new" | "learning" | "mastered") => {
      setBusyId(itemId);
      try {
        const updated = await updateProjectItem(projectId, itemId, status);
        setItems((current) => current.map((row) => (row.id === itemId ? updated : row)));
        setMissedItems((current) =>
          status === "mastered"
            ? current.filter((row) => row.id !== itemId)
            : current.map((row) => (row.id === itemId ? updated : row)),
        );
        onItemUpdated?.();
        return true;
      } catch {
        return false;
      } finally {
        setBusyId(null);
      }
    },
    [onItemUpdated, projectId, updateProjectItem],
  );

  return { items, missedItems, loading, busyId, loadError, load, changeStatus };
}
