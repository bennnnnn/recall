import { act, render } from "@testing-library/react-native";

import HomeScreen from "@/features/chat/screens/ChatScreen";
import { closeDrawer, openDrawer } from "@/lib/drawer";

/**
 * How often the whole chat screen renders while the drawer moves. Every hook
 * the screen calls is a stub except the keyboard inset, the layout metrics,
 * the body props and the drawer shell, so a render here is the screen
 * reacting to the drawer and nothing else.
 */

const mockChatRenders = jest.fn();
const mockNoop = () => {};
const mockAsyncNoop = async () => {};
const mockRef = { current: null };

const mockChat = {
  messages: [],
  setMessages: mockNoop,
  streaming: false,
  finalizing: false,
  sendingMessageId: null,
  sendMessage: mockAsyncNoop,
  rejectedSend: null,
  retryRejectedSend: mockNoop,
  restoreRejectedAttachmentDraft: mockNoop,
  beginRegenerateUi: mockNoop,
  cancelRegenerateUi: mockNoop,
  regenerateResponse: mockAsyncNoop,
  stopGeneration: mockNoop,
  connect: mockNoop,
};
const mockScroll = {
  listRef: mockRef,
  listBottomPadRef: { current: 0 },
  newMessageCountRef: { current: 0 },
  showScrollToBottom: false,
  scrollAwayCount: 0,
  scrollToLatest: mockNoop,
  handleScroll: mockNoop,
  handleScrollEnd: mockNoop,
  handleContentSizeChange: mockNoop,
  handleListLayout: mockNoop,
};
const mockRouteLoader = {
  handleFirstReply: mockAsyncNoop,
  chatTitle: null,
  setChatTitle: mockNoop,
  titleGenerating: false,
  pinned: false,
  setPinned: mockNoop,
  archived: false,
  setArchived: mockNoop,
  chatLoading: false,
  hasMoreOlder: false,
  loadingOlder: false,
  loadOlderMessages: mockAsyncNoop,
  highlightedMessageId: null,
  startNewChat: mockNoop,
};
const mockChatActions = {
  showActionBanner: mockNoop,
  menuVisible: false,
  setMenuVisible: mockNoop,
  renameVisible: false,
  renameText: "",
  setRenameText: mockNoop,
  setRenameVisible: mockNoop,
  actionBanner: null,
  dismissActionBanner: mockNoop,
  handleFeedback: mockNoop,
  handleSaveEmailDraft: async () => true,
  confirmRename: mockAsyncNoop,
  shareVisible: false,
  closeShare: mockNoop,
  loadTranscriptMessages: async () => [],
  onShareFromMenu: mockNoop,
  onExportPdfFromMenu: mockNoop,
  onRenameFromMenu: mockNoop,
  onTogglePinFromMenu: mockNoop,
  onToggleArchiveFromMenu: mockNoop,
  onDeleteFromMenu: mockNoop,
};
const mockSend = {
  setInput: mockNoop,
  pendingAttachment: null,
  removePendingAttachment: mockNoop,
  attachPicking: false,
  sendPhase: "idle",
  attachSheetOpen: false,
  setAttachSheetOpen: mockNoop,
  handleSend: mockAsyncNoop,
  restoreComposerDraft: mockNoop,
  handlePickAttachment: mockNoop,
  handleAttachmentSheetSelect: mockAsyncNoop,
  handleMathScanCaptured: mockNoop,
  readScan: async () => null,
  handleMathScanSolve: mockNoop,
  mathScannerOpen: false,
  setMathScannerOpen: mockNoop,
};
const mockLiveTalk = {
  open: mockNoop,
  close: mockNoop,
  toggle: mockAsyncNoop,
  toggleMute: mockNoop,
  yieldToComposer: mockNoop,
  visible: false,
  muted: false,
  phase: "idle",
  meterLevel: 0,
  recording: false,
};
const mockErrorHandlers = {
  chatError: null,
  handleChatError: mockNoop,
  handleStreamBusy: mockNoop,
  dismissChatError: mockNoop,
  handleRejectedSendChange: mockNoop,
};
const mockQuotaNudge = { show: false, usedPct: 0, dismiss: mockNoop };
const mockImageGen = { generating: false, cancel: mockNoop, submitPrompt: mockAsyncNoop, retry: mockNoop };
const mockDictation = {
  voiceInputAvailable: false,
  voiceRecording: false,
  voiceTranscribing: false,
  voiceMeterLevel: 0,
  toggleVoiceInput: mockAsyncNoop,
  cancelVoiceInput: mockNoop,
};
const mockDraft = { activeChatId: null, draftChatId: null };
const mockModels = { isPaid: false, autoEnabled: true, modelEnabledSet: new Set<string>(), AUTO_MODEL_ID: "auto" };
const mockComposerState = { selectedModel: "auto" };
const mockMessageList = { headerTitleLabel: null, renderItem: () => null };
const mockRegenerate = { regenerate: mockAsyncNoop, regenerating: false };
const mockAuth = { token: "token", user: null, updateUser: mockAsyncNoop };
const mockRouter = { push: mockNoop, replace: mockNoop, setParams: mockNoop };
const mockT = (key: string) => key;

jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 1 }));
jest.mock("expo-router", () => ({
  Redirect: () => null,
  useLocalSearchParams: () => ({}),
  useRouter: () => mockRouter,
}));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: mockT }) }));
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => mockAuth }));
jest.mock("@/components/ConversationList", () => ({ ConversationList: () => null }));
jest.mock("@/features/chat/components/ChatScreenBody", () => ({ ChatScreenBody: () => null }));
jest.mock("@/features/chat/components/ChatScreenMenuSheets", () => ({ ChatScreenMenuSheets: () => null }));
jest.mock("@/features/chat/components/ChatHeader", () => ({ ChatHeader: () => null }));
jest.mock("@/features/chat/components/ChatComposer", () => ({ COMPOSER_HEIGHT: 56 }));
jest.mock("@/features/attachments/components/ComposerAttachmentPreview", () => ({
  composerAttachmentExtra: () => 0,
}));
jest.mock("@/features/speech/components/LiveTalkOverlay", () => ({ LiveTalkOverlay: () => null }));
jest.mock("@/features/home/hooks/useHomeRefreshOnChatFocus", () => ({ useHomeRefreshOnChatFocus: () => {} }));
jest.mock("@/features/chat/hooks/useChat", () => ({
  useChat: () => {
    mockChatRenders();
    return mockChat;
  },
}));
jest.mock("@/features/chat/hooks/useChatActions", () => ({ useChatActions: () => mockChatActions }));
jest.mock("@/features/chat/hooks/useChatComposerState", () => ({ useChatComposerState: () => mockComposerState }));
jest.mock("@/features/chat/hooks/useComposerDictation", () => ({ useComposerDictation: () => mockDictation }));
jest.mock("@/features/chat/hooks/useChatDraftWarmup", () => ({ useChatDraftWarmup: () => {} }));
jest.mock("@/features/chat/hooks/useChatMessageList", () => ({ useChatMessageList: () => mockMessageList }));
jest.mock("@/features/chat/hooks/useChatRegenerate", () => ({ useChatRegenerate: () => mockRegenerate }));
jest.mock("@/features/chat/hooks/useChatRouteLoader", () => ({ useChatRouteLoader: () => mockRouteLoader }));
jest.mock("@/features/chat/hooks/useChatScroll", () => ({ useChatScroll: () => mockScroll }));
jest.mock("@/features/chat/hooks/useChatSend", () => ({ useChatSend: () => mockSend }));
jest.mock("@/features/speech/hooks/useLiveTalk", () => ({ useLiveTalk: () => mockLiveTalk }));
jest.mock("@/features/chat/hooks/useDraftChat", () => ({ useDraftChat: () => mockDraft }));
jest.mock("@/hooks/useModels", () => ({ useModels: () => mockModels }));
jest.mock("@/contexts/NetworkContext", () => ({ useNetwork: () => ({ isOffline: false }) }));
jest.mock("@/features/chat/hooks/useChatScreenError", () => ({
  useChatErrorHandlers: () => mockErrorHandlers,
  useChatErrorRecovery: () => mockNoop,
  useChatStreamLifecycle: () => mockQuotaNudge,
}));
jest.mock("@/features/todos/context/TodosContext", () => ({ useTodosOptional: () => null }));
jest.mock("@/features/images/hooks/useImageGeneration", () => ({ useImageGeneration: () => mockImageGen }));

async function rendersDuring(step: () => void): Promise<number> {
  const before = mockChatRenders.mock.calls.length;
  await act(async () => {
    step();
  });
  return mockChatRenders.mock.calls.length - before;
}

describe("ChatScreen renders", () => {
  it("does not render when the drawer opens or closes", async () => {
    await render(<HomeScreen />);

    const open = await rendersDuring(() => openDrawer());
    const close = await rendersDuring(() => closeDrawer());

    expect({ open, close }).toEqual({ open: 0, close: 0 });
  });
});
