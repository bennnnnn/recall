import React from "react";
import { Text } from "react-native";
import { render } from "@testing-library/react-native";

import {
  ChatScreenBody,
  type ChatScreenBodyProps,
} from "@/features/chat/components/ChatScreenBody";
import type { Message } from "@/lib/api";
import { lightTheme } from "@/lib/theme";

const mockChatMessageList = jest.fn();
const mockChatComposer = jest.fn();
const mockAttachmentSourceSheet = jest.fn();

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

jest.mock("@/features/chat/components/ChatMessageList", () => ({
  ChatMessageList: (props: {
    messages: Message[];
    renderItem: (info: {
      item: Message;
      index: number;
      target: "Cell";
      extraData: unknown;
    }) => React.ReactElement | null;
  }) => {
    const { View: MockView } = jest.requireActual("react-native") as typeof import("react-native");
    mockChatMessageList(props);
    return (
      <MockView testID="message-list">
        {props.messages[0]
          ? props.renderItem({
              item: props.messages[0],
              index: 0,
              target: "Cell",
              extraData: undefined,
            })
          : null}
      </MockView>
    );
  },
}));

jest.mock("@/features/chat/components/ChatComposer", () => ({
  ChatComposer: (props: { streaming: boolean }) => {
    const { View: MockView } = jest.requireActual("react-native") as typeof import("react-native");
    mockChatComposer(props);
    return <MockView testID={props.streaming ? "composer-streaming" : "composer-idle"} />;
  },
}));

jest.mock("@/contexts/StreamingDraftContext", () => ({
  StreamingDraftProvider: ({ children }: { children: React.ReactNode }) => children,
}));

jest.mock("@/ui/feedback/ActionBanner", () => ({ ActionBanner: () => null }));
jest.mock("@/features/attachments/components/AttachmentSourceSheet", () => ({
  AttachmentSourceSheet: (props: { visible?: boolean }) => {
    mockAttachmentSourceSheet(props);
    return null;
  },
}));
jest.mock("@/components/MathEquationScanner", () => ({
  MathEquationScanner: () => null,
}));
jest.mock("@/components/UpgradeSheet", () => ({ UpgradeSheet: () => null }));
jest.mock("@/features/chat/components/ChatInlineError", () => ({ ChatInlineError: () => null }));
jest.mock("@/features/chat/components/ChatQuotaNudge", () => ({ ChatQuotaNudge: () => null }));
jest.mock("@/features/chat/components/ChatScrollFab", () => ({ ChatScrollFab: () => null }));

const noop = jest.fn();
const message: Message = {
  id: "message-1",
  role: "assistant",
  content: "Hello",
  model: "free-chat",
  created_at: "2026-09-19T00:00:00Z",
};
const renderItem = jest.fn(({ item }: { item: Message }) => <Text>{item.content}</Text>);
const onScroll = jest.fn();
const onScrollEnd = jest.fn();
const onLoadOlder = jest.fn();

const baseProps: ChatScreenBodyProps = {
  layout: {
    styles: { container: {} } as never,
    theme: lightTheme,
    drawerOpen: false,
    composerClearance: 96,
    headerInset: 72,
    listBottomPad: 104,
    emptyHeight: 500,
  },
  list: {
    listRef: { current: null },
    messages: [message],
    hasMoreOlder: false,
    loadingOlder: false,
    chatLoading: false,
    routeChatId: "chat-1",
    renderItem,
    onLoadOlder,
    onScroll,
    onScrollEnd,
    header: null,
  },
  composer: {
    streaming: false,
    attachPicking: false,
    sendBusy: false,
    pendingAttachment: null,
    onRemoveAttachment: noop,
    onPickAttachment: noop,
    onSend: noop,
    onStop: noop,
    isOffline: false,
    voiceAvailable: true,
    voiceRecording: false,
    voiceTranscribing: false,
    voiceMeterLevel: 0.12,
  },
  chrome: {
    actionBanner: null,
    onDismissActionBanner: noop,
    showScrollToBottom: false,
    scrollAwayCount: 0,
    onScrollToLatest: noop,
    quotaNudgeVisible: false,
    quotaUsedPct: 0,
    onQuotaUpgrade: noop,
    onQuotaDismiss: noop,
    chatError: null,
    isPaid: false,
    onUpgrade: noop,
    onRetryChatError: noop,
    onChangeModel: noop,
    onDismissChatError: noop,
  },
  sheets: {
    attachSheetOpen: false,
    onCloseAttachSheet: noop,
    onAttachmentSource: noop,
    mathScannerOpen: false,
    onCloseMathScanner: noop,
    onMathScanCaptured: noop,
    onReadScan: async () => null,
    onMathScanSolve: noop,
    upgradeVisible: false,
    onCloseUpgrade: noop,
  },
};

describe("ChatScreenBody", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the grouped screen contract and forwards stable list callbacks", async () => {
    const { getByText, getByTestId, rerender } = await render(
      <ChatScreenBody {...baseProps} />,
    );

    expect(getByText("Hello")).toBeTruthy();
    expect(getByTestId("composer-idle")).toBeTruthy();
    expect(mockChatMessageList).toHaveBeenLastCalledWith(
      expect.objectContaining({
        renderItem,
        onLoadOlder,
        onScroll,
        onScrollEnd,
        headerInset: 72,
        streamActive: false,
      }),
    );

    await rerender(
      <ChatScreenBody
        {...baseProps}
        composer={{ ...baseProps.composer, streaming: true }}
      />,
    );

    expect(getByTestId("composer-streaming")).toBeTruthy();
    expect(mockAttachmentSourceSheet).toHaveBeenLastCalledWith(
      expect.objectContaining({ visible: false }),
    );
    expect(mockAttachmentSourceSheet.mock.calls.at(-1)?.[0]).not.toHaveProperty("bottomOffset");
    expect(mockChatMessageList).toHaveBeenLastCalledWith(
      expect.objectContaining({
        renderItem,
        onLoadOlder,
        onScroll,
        onScrollEnd,
        streamActive: true,
      }),
    );
  });

  it("shows a busy Send, not Stop, while a send is on its way; the list still follows the dots", async () => {
    const { getByTestId } = await render(
      <ChatScreenBody
        {...baseProps}
        composer={{ ...baseProps.composer, streaming: true, sendBusy: true }}
      />,
    );
    expect(getByTestId("composer-idle")).toBeTruthy();
    expect(mockChatComposer).toHaveBeenLastCalledWith(expect.objectContaining({ streaming: false, sendBusy: true }));
    expect(mockChatMessageList).toHaveBeenLastCalledWith(expect.objectContaining({ streamActive: true }));
  });
});
