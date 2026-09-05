import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { Chat } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import {
  clearChatSelection,
  selectAllChatIds,
  toggleChatSelection,
} from "@/lib/drawerChatSelection";

type Params = {
  token: string | null;
  isDrawerOpen: boolean;
  listedChats: Chat[];
};

export function useDrawerChatSelection({ token, isDrawerOpen, listedChats }: Params) {
  const session = getSessionGeneration();
  const signedIn = Boolean(token);
  const viewRef = useRef({ session, signedIn, isDrawerOpen });
  if (viewRef.current.session !== session || viewRef.current.signedIn !== signedIn || viewRef.current.isDrawerOpen !== isDrawerOpen) {
    viewRef.current = { session, signedIn, isDrawerOpen };
  }
  const view = viewRef.current;
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const currentView = useCallback(
    () => mounted.current && signedIn && isDrawerOpen && viewRef.current === view && session === getSessionGeneration(),
    [signedIn, isDrawerOpen, view, session],
  );
  const [selectionMode, setSelectionMode] = useState(false);
  const [requestedIds, setRequestedIds] = useState<Set<string>>(() => new Set());
  const selectionVersion = useRef(0);
  const version = selectionVersion.current;

  useEffect(() => {
    selectionVersion.current++;
    setSelectionMode(false);
    setRequestedIds(clearChatSelection());
  }, [view]);

  // Preserve intent through optimistic removal, so failed rows regain their
  // checkmark on rollback. Missing rows never inflate the actionable count.
  const selectedIds = useMemo(() => new Set(
    listedChats.filter((chat) => requestedIds.has(chat.id)).map((chat) => chat.id),
  ), [listedChats, requestedIds]);

  const enterSelectionMode = useCallback((initialChatId?: string) => {
    if (!currentView()) return;
    selectionVersion.current++;
    setSelectionMode(true);
    setRequestedIds(initialChatId ? new Set([initialChatId]) : clearChatSelection());
  }, [currentView]);

  const exitSelectionMode = useCallback(() => {
    if (!currentView() || version !== selectionVersion.current) return;
    selectionVersion.current++;
    setSelectionMode(false);
    setRequestedIds(clearChatSelection());
  }, [currentView, version]);

  const toggleSelected = useCallback((chatId: string) => {
    if (!currentView() || !selectionMode || version !== selectionVersion.current) return;
    setRequestedIds((prev) => toggleChatSelection(prev, chatId));
  }, [currentView, selectionMode, version]);

  const selectAllListed = useCallback(() => {
    if (!currentView() || !selectionMode || version !== selectionVersion.current) return;
    setRequestedIds(selectAllChatIds(listedChats));
  }, [currentView, selectionMode, version, listedChats]);

  return {
    selectionMode,
    selectedIds,
    selectedCount: selectedIds.size,
    enterSelectionMode,
    exitSelectionMode,
    toggleSelected,
    selectAllListed,
  };
}
