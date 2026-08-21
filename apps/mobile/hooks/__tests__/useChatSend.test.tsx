import React from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";

import { useChatSend } from "@/hooks/useChatSend";

const inputRef = { current: "hello" };
jest.mock("@/contexts/ComposerDraftContext", () => ({
  useComposerDraftApi: () => ({ setInput: jest.fn(), inputRef }),
}));
jest.mock("expo-router", () => ({
  useRouter: () => ({ setParams: jest.fn() }),
}));
jest.mock("@/lib/attachments", () => ({
  pickDocument: jest.fn(),
  pickFromCamera: jest.fn(),
  pickFromPhotoLibrary: jest.fn(),
  uploadChatAttachment: jest.fn(),
  messageTextForSend: jest.fn(),
  defaultMathCameraPrompt: "Solve this",
  HeicUnsupportedError: class extends Error {},
}));
jest.mock("@/lib/haptics", () => ({
  tap: jest.fn(),
  notifyWarning: jest.fn(),
}));
jest.mock("@/lib/resolveClientGeoForQuery", () => ({
  resolveClientGeoForQuery: jest.fn(async () => ({ ok: true, clientGeo: null })),
}));
jest.mock("@/lib/scheduleIdle", () => ({
  scheduleIdlePromise: (callback: () => unknown) => Promise.resolve(callback()),
}));

let current: ReturnType<typeof useChatSend>;
const onOfflineBlocked = jest.fn();
const onGenerateImage = jest.fn();

function Probe({ offline = false }: { offline?: boolean }) {
  current = useChatSend({
    token: "token",
    chatId: null,
    setChatId: jest.fn(),
    setChatTitle: jest.fn(),
    router: { setParams: jest.fn() } as never,
    draft: {
      draftChatIdRef: { current: null },
      skipLoadForChatIdRef: { current: null },
      creatingRef: { current: false },
      prepareDraftChat: jest.fn(),
      setDraftChatId: jest.fn(),
    } as never,
    scroll: { newMessageCountRef: { current: 0 } } as never,
    streaming: false,
    sendMessage: jest.fn(),
    editMessage: jest.fn(),
    setMessages: jest.fn(),
    messages: [],
    selectedModel: "free-chat",
    pendingLaunch: null,
    setPendingLaunch: jest.fn(),
    pendingLaunchRef: { current: null },
    user: null,
    updateUser: jest.fn(),
    t: (key) => key,
    isOffline: offline,
    onOfflineBlocked,
    onGenerateImage,
  });
  return <Text>send</Text>;
}

describe("useChatSend", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    inputRef.current = "hello";
  });

  it("keeps the draft and surfaces the offline callback", async () => {
    await act(async () => {
      render(<Probe offline />);
    });
    await act(async () => {
      await current.handleSend();
    });
    expect(onOfflineBlocked).toHaveBeenCalledTimes(1);
  });

  it("routes image intent directly to generation", async () => {
    inputRef.current = "Generate an image of a lighthouse";
    await act(async () => {
      render(<Probe />);
    });
    await act(async () => {
      await current.handleSend();
    });
    expect(onGenerateImage).toHaveBeenCalledWith(
      "a lighthouse",
      "Generate an image of a lighthouse",
    );
  });
});
