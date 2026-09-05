import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";
import { useAuthToken } from "@/contexts/AuthContext";
import { getSessionGeneration } from "@/lib/auth";
import {
  fetchProjectDetail,
  getCachedProjectDetail,
  subscribeProjectDetailCache,
} from "@/lib/cache/projectDetailCache";

export function useProjectDetail(projectId: string | undefined) {
  const token = useAuthToken();
  const tokenRef = useRef(token);
  tokenRef.current = token;
  const session = getSessionGeneration();
  const signedIn = Boolean(token);
  const owner = useMemo(() => ({ session, projectId, signedIn }), [session, projectId, signedIn]);
  const ownerRef = useRef(owner);
  ownerRef.current = owner;
  const active = useRef(false);
  const request = useRef(0);
  const initial = signedIn && projectId ? (getCachedProjectDetail(projectId) ?? null) : null;
  const [state, setState] = useState({
    owner,
    project: initial,
    loading: !initial,
    loadError: false,
  });
  const view =
    state.owner === owner ? state : { project: initial, loading: !initial, loadError: false };
  const isCurrentOwner = useCallback(
    () =>
      active.current &&
      ownerRef.current === owner &&
      owner.signedIn &&
      owner.session === getSessionGeneration(),
    [owner],
  );
  const load = useCallback(
    async (options?: { silent?: boolean; force?: boolean; afterPending?: boolean }) => {
      if (!tokenRef.current || !owner.projectId || !isCurrentOwner()) return;
      const ticket = ++request.current;
      setState((prev) => ({
        ...prev,
        owner,
        project: prev.owner === owner ? prev.project : null,
        loading: prev.owner !== owner || !prev.project,
        loadError: false,
      }));
      const data = await fetchProjectDetail(tokenRef.current, owner.projectId, options);
      if (!isCurrentOwner() || request.current !== ticket) return;
      setState((prev) => ({
        owner,
        project: data ?? (prev.owner === owner ? prev.project : null),
        loading: false,
        loadError: data === null,
      }));
    },
    [owner, isCurrentOwner],
  );
  useEffect(
    () =>
      subscribeProjectDetailCache(() => {
        if (!owner.projectId || !isCurrentOwner()) return;
        const project = getCachedProjectDetail(owner.projectId);
        if (project) setState((prev) => ({ ...prev, owner, project, loading: false }));
      }),
    [owner, isCurrentOwner],
  );
  useFocusEffect(
    useCallback(() => {
      active.current = true;
      void load({ force: true });
      return () => {
        active.current = false;
        request.current += 1;
      };
    }, [load]),
  );
  return { ...view, load, isCurrentOwner };
}
