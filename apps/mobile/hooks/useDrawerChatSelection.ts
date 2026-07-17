import { useCallback, useEffect, useState } from "react";

import type { Chat } from "@/lib/api";
import {
  clearChatSelection,
  selectAllChatIds,
  toggleChatSelection,
} from "@/lib/drawerChatSelection";

type Params = {
  isDrawerOpen: boolean;
  listedChats: Chat[];
};

export function useDrawerChatSelection({ isDrawerOpen, listedChats }: Params) {
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    if (!isDrawerOpen) {
      setSelectionMode(false);
      setSelectedIds(clearChatSelection());
    }
  }, [isDrawerOpen]);

  /** Enter multi-select; optionally pre-check `initialChatId` (from long-press → Select). */
  const enterSelectionMode = useCallback((initialChatId?: string) => {
    setSelectionMode(true);
    setSelectedIds(initialChatId ? new Set([initialChatId]) : clearChatSelection());
  }, []);

  const exitSelectionMode = useCallback(() => {
    setSelectionMode(false);
    setSelectedIds(clearChatSelection());
  }, []);

  const toggleSelected = useCallback((chatId: string) => {
    setSelectedIds((prev) => toggleChatSelection(prev, chatId));
  }, []);

  const selectAllListed = useCallback(() => {
    setSelectedIds(selectAllChatIds(listedChats));
  }, [listedChats]);

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
