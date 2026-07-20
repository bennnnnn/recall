import { ChatActionsSheet } from "@/components/ChatActionsSheet";
import { ChatRenameSheet } from "@/components/ChatRenameSheet";

type Props = {
  menuVisible: boolean;
  chatTitle: string | null;
  pinned: boolean;
  archived: boolean;
  onCloseMenu: () => void;
  onShare: () => void;
  onRename: () => void;
  onTogglePin: () => void;
  onToggleArchive: () => void;
  onDelete: () => void;
  onOpenModels?: () => void;
  renameVisible: boolean;
  renameText: string;
  onRenameTextChange: (text: string) => void;
  onCloseRename: () => void;
  onConfirmRename: () => void;
};

export function ChatScreenMenuSheets({
  menuVisible,
  chatTitle,
  pinned,
  archived,
  onCloseMenu,
  onShare,
  onRename,
  onTogglePin,
  onToggleArchive,
  onDelete,
  onOpenModels,
  renameVisible,
  renameText,
  onRenameTextChange,
  onCloseRename,
  onConfirmRename,
}: Props) {
  return (
    <>
      <ChatActionsSheet
        visible={menuVisible}
        title={chatTitle}
        pinned={pinned}
        archived={archived}
        onClose={onCloseMenu}
        onShare={onShare}
        onRename={onRename}
        onTogglePin={onTogglePin}
        onToggleArchive={onToggleArchive}
        onDelete={onDelete}
        onOpenModels={onOpenModels}
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
