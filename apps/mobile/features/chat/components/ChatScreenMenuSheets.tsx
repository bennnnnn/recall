import type { RefObject } from "react";
import type { HostInstance } from "react-native";

import { ChatActionsMenu } from "@/features/chat/components/ChatActionsMenu";
import { ChatRenameSheet } from "@/features/chat/components/ChatRenameSheet";

export type ChatScreenMenuSheetsProps = {
  menuVisible: boolean;
  /** The header ⋮ button the menu drops from. */
  menuAnchorRef: RefObject<HostInstance | null>;
  chatTitle: string | null;
  pinned: boolean;
  archived: boolean;
  onCloseMenu: () => void;
  onShare: () => void;
  onExportPdf: () => void;
  onRename: () => void;
  onTogglePin: () => void;
  onToggleArchive: () => void;
  onDelete: () => void;
  renameVisible: boolean;
  renameText: string;
  onRenameTextChange: (text: string) => void;
  onCloseRename: () => void;
  onConfirmRename: () => void;
};

export function ChatScreenMenuSheets({
  menuVisible,
  menuAnchorRef,
  chatTitle,
  pinned,
  archived,
  onCloseMenu,
  onShare,
  onExportPdf,
  onRename,
  onTogglePin,
  onToggleArchive,
  onDelete,
  renameVisible,
  renameText,
  onRenameTextChange,
  onCloseRename,
  onConfirmRename,
}: ChatScreenMenuSheetsProps) {
  return (
    <>
      <ChatActionsMenu
        visible={menuVisible}
        anchorRef={menuAnchorRef}
        title={chatTitle}
        pinned={pinned}
        archived={archived}
        onClose={onCloseMenu}
        onShare={onShare}
        onExportPdf={onExportPdf}
        onRename={onRename}
        onTogglePin={onTogglePin}
        onToggleArchive={onToggleArchive}
        onDelete={onDelete}
      />
      <ChatRenameSheet
        visible={renameVisible}
        value={renameText}
        onChangeText={onRenameTextChange}
        onClose={onCloseRename}
        onSave={onConfirmRename}
      />
    </>
  );
}
