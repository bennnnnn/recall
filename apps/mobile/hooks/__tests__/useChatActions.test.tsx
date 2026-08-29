import React from "react";
import { Alert, Text } from "react-native";
import { act, render } from "@testing-library/react-native";

import { useChatActions } from "@/hooks/useChatActions";
import { api } from "@/lib/api";
import { insertChatGlobal, patchChatGlobal, removeChatGlobal } from "@/lib/drawer";

jest.mock("@/lib/api", () => ({
  api: {
    renameChat: jest.fn(),
    deleteChat: jest.fn(),
    setPin: jest.fn(),
    setArchive: jest.fn(),
    setMessageFeedback: jest.fn(),
    listAllMessages: jest.fn(),
  },
}));

jest.mock("@/lib/drawer", () => ({
  insertChatGlobal: jest.fn(),
  moveChatArchiveGlobal: jest.fn(),
  patchChatGlobal: jest.fn(),
  removeChatGlobal: jest.fn(),
}));

jest.mock("@/lib/chatMessageCache", () => ({
  clearCachedChatMessages: jest.fn(),
}));

jest.mock("@/lib/exportMessagePdf", () => ({
  exportConversationAsPdf: jest.fn(),
}));

jest.mock("@/lib/exportPdf", () => ({
  isShareCancelled: jest.fn(() => false),
}));

jest.mock("@/lib/share", () => ({
  shareConversation: jest.fn(),
}));

jest.mock("@/lib/haptics", () => ({
  tap: jest.fn(),
}));

const mockFeedbackError = jest.fn();
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => ({ error: mockFeedbackError }),
}));

const setChatTitle = jest.fn();

let actions: ReturnType<typeof useChatActions>;

function Probe() {
  actions = useChatActions({
    token: "tok",
    chatId: "chat-1",
    chatTitle: "Old title",
    messages: [],
    pinned: false,
    setPinned: jest.fn(),
    archived: false,
    setArchived: jest.fn(),
    setChatTitle,
    setMessages: jest.fn(),
    router: { canGoBack: () => false, back: jest.fn(), replace: jest.fn() } as never,
    t: (key) => key,
  });
  return <Text>chat actions</Text>;
}

describe("useChatActions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(Alert, "alert").mockImplementation(() => {});
    mockFeedbackError.mockClear();
  });

  it("renames the chat immediately and rolls back on failure", async () => {
    (api.renameChat as jest.Mock).mockRejectedValue(new Error("fail"));
    await act(async () => {
      render(<Probe />);
    });

    await act(async () => {
      actions.setRenameText("New title");
    });
    await act(async () => {
      await actions.confirmRename();
    });

    expect(setChatTitle).toHaveBeenCalledWith("New title");
    expect(patchChatGlobal).toHaveBeenCalledWith("chat-1", { title: "New title" });
    expect(setChatTitle).toHaveBeenCalledWith("Old title");
    expect(patchChatGlobal).toHaveBeenCalledWith("chat-1", { title: "Old title" });
    expect(mockFeedbackError).toHaveBeenCalledWith("chat.rename_failed");
    expect(Alert.alert).not.toHaveBeenCalled();
  });

  it("restores the drawer row when delete fails", async () => {
    (api.deleteChat as jest.Mock).mockRejectedValue(new Error("fail"));
    let deletePress: (() => void | Promise<void>) | undefined;
    (Alert.alert as jest.Mock).mockImplementation((_title, _body, buttons) => {
      const press = (
        buttons as { text: string; onPress?: () => void | Promise<void> }[] | undefined
      )?.find((b) => b.text === "common.delete")?.onPress;
      if (press) deletePress = press;
    });
    await act(async () => {
      render(<Probe />);
    });

    await act(async () => {
      actions.confirmDelete();
    });
    await act(async () => {
      await deletePress?.();
    });

    expect(removeChatGlobal).toHaveBeenCalledWith("chat-1");
    expect(insertChatGlobal).toHaveBeenCalledWith(
      expect.objectContaining({ id: "chat-1", title: "Old title" }),
    );
  });

  it("keeps the ⋮ sheet open until Share.share is presented", async () => {
    (api.listAllMessages as jest.Mock).mockResolvedValue([
      { id: "m1", role: "user", content: "hi" },
    ]);
    const { shareConversation } = jest.requireMock("@/lib/share") as {
      shareConversation: jest.Mock;
    };
    let visibleWhileSharing = false;
    shareConversation.mockImplementation(async () => {
      visibleWhileSharing = actions.menuVisible;
    });

    await act(async () => {
      render(<Probe />);
    });
    await act(async () => {
      actions.setMenuVisible(true);
    });
    await act(async () => {
      await actions.handleShare();
    });

    expect(shareConversation).toHaveBeenCalled();
    expect(visibleWhileSharing).toBe(true);
    expect(actions.menuVisible).toBe(false);
  });

  it("reports share failure through ActionFeedback", async () => {
    (api.listAllMessages as jest.Mock).mockResolvedValue([
      { id: "m1", role: "user", content: "hi" },
    ]);
    const { shareConversation } = jest.requireMock("@/lib/share") as {
      shareConversation: jest.Mock;
    };
    shareConversation.mockRejectedValue(new Error("fail"));

    await act(async () => {
      render(<Probe />);
    });
    await act(async () => {
      await actions.handleShare();
    });

    expect(mockFeedbackError).toHaveBeenCalledWith("chat.share_failed");
    expect(Alert.alert).not.toHaveBeenCalled();
    expect(actions.menuVisible).toBe(false);
  });
});
