import { ChatActionsSheet } from "@/components/ChatActionsSheet";
import { ChatRenameSheet } from "@/components/ChatRenameSheet";

type Props = {
  menuVisible: boolean;
  chatTitle: string | null;
  pinned: boolean;
  onCloseMenu: () => void;
  onShare: () => void;
  onRename: () => void;
  onTogglePin: () => void;
  onDelete: () => void;
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
  onCloseMenu,
  onShare,
  onRename,
  onTogglePin,
  onDelete,
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
        onClose={onCloseMenu}
        onShare={onShare}
        onRename={onRename}
        onTogglePin={onTogglePin}
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
