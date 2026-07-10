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

  const enterSelectionMode = useCallback(() => {
    setSelectionMode(true);
    setSelectedIds(clearChatSelection());
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
