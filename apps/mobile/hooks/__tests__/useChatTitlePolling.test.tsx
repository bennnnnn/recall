import React, { useState } from "react";
import { Text } from "react-native";
import { act, render, waitFor } from "@testing-library/react-native";

import { useChatTitlePolling } from "@/hooks/useChatTitlePolling";

jest.mock("@/lib/api", () => ({
  api: {
    getChat: jest.fn(),
  },
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
import { patchChatGlobal, setChatTitleGenerating } from "@/lib/drawer";

const getChat = api.getChat as jest.Mock;
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
});
