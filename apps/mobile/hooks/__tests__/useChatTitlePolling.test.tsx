import React, { useState } from "react";
import { Text } from "react-native";
import { act, render, waitFor } from "@testing-library/react-native";

import { useChatTitlePolling } from "@/hooks/useChatTitlePolling";

jest.mock("@/lib/api", () => ({
  api: {
    getChat: jest.fn(),
  },
}));

jest.mock("@/lib/cache/chatListCache", () => ({
  getCachedChat: jest.fn(),
  peekCreatedChat: jest.fn(),
}));

jest.mock("@/lib/drawer", () => {
  let pending: string | null = null;
  return {
    insertChatGlobal: jest.fn(),
    patchChatGlobal: jest.fn(),
    setChatTitleGenerating: jest.fn((id: string | null) => {
      pending = id;
    }),
    isChatTitleGenerating: jest.fn((id: string) => pending === id),
  };
});

import { api } from "@/lib/api";
import { getCachedChat, peekCreatedChat } from "@/lib/cache/chatListCache";
import { insertChatGlobal, patchChatGlobal, setChatTitleGenerating } from "@/lib/drawer";

const getChat = api.getChat as jest.Mock;
const peekCreated = peekCreatedChat as jest.Mock;
const listedChat = getCachedChat as jest.Mock;
const insertChat = insertChatGlobal as jest.Mock;
const patchChat = patchChatGlobal as jest.Mock;
const setGenerating = setChatTitleGenerating as jest.Mock;

type Polling = ReturnType<typeof useChatTitlePolling>;
let current: Polling;
let screenTitle: string | null = null;

function Probe({ chatId }: { chatId: string | null }) {
  const [title, setTitle] = useState<string | null>(null);
  screenTitle = title;
  current = useChatTitlePolling({
    token: "tok",
    chatId,
    setChatTitle: setTitle,
  });
  return <Text>{title ?? "none"}</Text>;
}

describe("useChatTitlePolling", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    screenTitle = null;
    setGenerating(null);
    peekCreated.mockReturnValue(undefined);
    listedChat.mockReturnValue(undefined);
    getChat.mockResolvedValue({ title: "A's title" });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("does not apply a title from chat A after navigating to chat B", async () => {
    const view = await act(async () => render(<Probe chatId="chat-a" />));
    await act(async () => {
      void current.pollForTitle("tok", "chat-a");
    });

    await act(async () => {
      view.rerender(<Probe chatId="chat-b" />);
    });

    await act(async () => {
      jest.advanceTimersByTime(2000);
    });

    expect(getChat).not.toHaveBeenCalled();
    expect(screenTitle).toBeNull();
    expect(patchChat).not.toHaveBeenCalled();
  });

  it("drops an in-flight title once the screen has moved to another chat", async () => {
    let resolveGet: (value: { title: string }) => void = () => {};
    getChat.mockImplementation(
      () =>
        new Promise<{ title: string }>((resolve) => {
          resolveGet = resolve;
        }),
    );

    const view = await act(async () => render(<Probe chatId="chat-a" />));
    await act(async () => {
      void current.pollForTitle("tok", "chat-a");
    });

    await act(async () => {
      jest.advanceTimersByTime(2000);
    });
    await waitFor(() => {
      expect(getChat).toHaveBeenCalledWith("tok", "chat-a");
    });

    await act(async () => {
      view.rerender(<Probe chatId="chat-b" />);
    });

    await act(async () => {
      resolveGet({ title: "A's title" });
    });

    expect(screenTitle).toBeNull();
    expect(patchChat).not.toHaveBeenCalled();
  });

  it("inserts the POST /chats row without GET /chats/{id}", async () => {
    const created = {
      id: "chat-a",
      title: null,
      model: "free-chat",
      pinned: false,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    peekCreated.mockReturnValue(created);

    await act(async () => {
      render(<Probe chatId="chat-a" />);
    });
    await act(async () => {
      void current.handleFirstReply();
    });

    expect(insertChat).toHaveBeenCalledWith(created);
    expect(getChat).not.toHaveBeenCalled();

    await act(async () => {
      jest.advanceTimersByTime(10000);
    });
    expect(getChat).not.toHaveBeenCalled();
  });

  it("does not GET or poll when the drawer row already has a title", async () => {
    listedChat.mockReturnValue({
      id: "chat-a",
      title: "Homework",
      model: "free-chat",
      pinned: false,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });

    await act(async () => {
      render(<Probe chatId="chat-a" />);
    });
    await act(async () => {
      await current.handleFirstReply();
    });

    expect(getChat).not.toHaveBeenCalled();
    expect(screenTitle).toBe("Homework");

    await act(async () => {
      jest.advanceTimersByTime(10000);
    });
    expect(getChat).not.toHaveBeenCalled();
  });
});
