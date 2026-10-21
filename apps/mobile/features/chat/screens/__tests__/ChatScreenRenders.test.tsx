import { act, render } from "@testing-library/react-native";

import HomeScreen from "@/features/chat/screens/ChatScreen";
import { closeDrawer, openDrawer } from "@/lib/drawer";

/**
 * How often the whole chat screen renders while the keyboard and the drawer
 * move. Every hook the screen calls is a stub except the keyboard inset, the
 * layout metrics, the body props and the drawer shell, so a render here is
 * the screen reacting to the keyboard or the drawer and nothing else.
 */

type KeyboardFrame = { state: number; height: number };
type Reaction = { previous: unknown; run: () => void };

jest.mock("react-native-reanimated", () => {
  const React = jest.requireActual("react") as typeof import("react");
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  const keyboard = { state: { value: 0 }, height: { value: 0 } };
  const reactions = new Set<Reaction>();
  const id = <T,>(value: T) => value;
  return {
    __esModule: true,
    default: { View, createAnimatedComponent: id },
    createAnimatedComponent: id,
    runOnJS: id,
    withSpring: id,
    withTiming: id,
    useAnimatedKeyboard: () => keyboard,
    useAnimatedStyle: (factory: () => object) => factory(),
    useSharedValue: <T,>(value: T) => React.useRef({ value }).current,
    useDerivedValue: <T,>(factory: () => T) => {
      const latest = React.useRef(factory);
      latest.current = factory;
      return React.useRef({
        get value() {
          return latest.current();
        },
      }).current;
    },
    // Runs like a mapper: on every keyboard frame, with the previous result.
    useAnimatedReaction: <T,>(prepare: () => T, react: (next: T, previous: T | null) => void) => {
      const latest = React.useRef({ prepare, react });
      latest.current = { prepare, react };
      React.useEffect(() => {
        const entry: Reaction = {
          previous: null,
          run: () => {
            const next = latest.current.prepare();
            latest.current.react(next, entry.previous as T | null);
            entry.previous = next;
          },
        };
        reactions.add(entry);
        return () => {
          reactions.delete(entry);
        };
      }, []);
    },
    mockEmitKeyboard(frame: KeyboardFrame) {
      keyboard.state.value = frame.state;
      keyboard.height.value = frame.height;
      reactions.forEach((reaction) => reaction.run());
    },
  };
});

const mockChatRenders = jest.fn();
const mockScrollOptions = jest.fn();
const mockBodyProps = jest.fn();
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
jest.mock("@/features/chat/components/ChatScreenBody", () => ({
  ChatScreenBody: (props: unknown) => {
    mockBodyProps(props);
    return null;
  },
}));
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
jest.mock("@/features/chat/hooks/useChatScroll", () => ({
  useChatScroll: (options: unknown) => {
    mockScrollOptions(options);
    return mockScroll;
  },
}));
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

const { mockEmitKeyboard } = jest.requireMock("react-native-reanimated") as {
  mockEmitKeyboard: (frame: KeyboardFrame) => void;
};

const OPENING = 1;
const OPEN = 2;
const CLOSING = 3;
const CLOSED = 4;
const KEYBOARD_HEIGHT = 336;
const FRAMES = 30;

/** Reanimated's iOS estimate of the keyboard curve (REAKeyboardEventObserver), one value per frame. */
function curve(a2: number, b1: number, b2: number, c1: number, c2: number): number[] {
  return Array.from({ length: FRAMES }, (_, frame) => {
    const x = (frame + 1) / FRAMES;
    return 1 - (1 - x) ** a2 - b1 * x * (1 - x) ** b2 - c1 * x ** 2 * (1 - x) ** c2;
  });
}

const openingFrames: KeyboardFrame[] = curve(4.62, 2.44, 9.82, 0.22, 2.09).map((progress) => ({
  state: OPENING,
  height: Math.round(KEYBOARD_HEIGHT * progress),
}));
const closingFrames: KeyboardFrame[] = curve(5.65, 2.74, 8.38, 0.93, 3.29).map((progress) => ({
  state: CLOSING,
  height: Math.round(KEYBOARD_HEIGHT * (1 - progress)),
}));

/** Each step runs in its own act, the way each keyboard frame reaches JS in its own task. */
async function rendersDuring(steps: (() => void)[]): Promise<number> {
  const before = mockChatRenders.mock.calls.length;
  for (const step of steps) {
    await act(async () => {
      step();
    });
  }
  return mockChatRenders.mock.calls.length - before;
}

const emitAll = (frames: KeyboardFrame[]) => frames.map((frame) => () => mockEmitKeyboard(frame));

describe("ChatScreen renders", () => {
  beforeEach(() => {
    // Nothing is mounted yet, so this only puts the shared keyboard back down.
    mockEmitKeyboard({ state: CLOSED, height: 0 });
  });

  it("renders once per keyboard show and once per hide, with the settled height", async () => {
    await render(<HomeScreen />);

    const show = await rendersDuring(
      emitAll([...openingFrames, { state: OPEN, height: KEYBOARD_HEIGHT }]),
    );
    expect(mockScrollOptions).toHaveBeenLastCalledWith(
      expect.objectContaining({ keyboardHeight: KEYBOARD_HEIGHT }),
    );

    const hide = await rendersDuring(emitAll([...closingFrames, { state: CLOSED, height: 0 }]));
    expect(mockScrollOptions).toHaveBeenLastCalledWith(expect.objectContaining({ keyboardHeight: 0 }));

    expect({ show, hide }).toEqual({ show: 1, hide: 1 });
  });

  it("moves the list space and the chrome with each keyboard frame while React holds the resting layout", async () => {
    await render(<HomeScreen />);
    type BodyLayout = {
      keyboardLift: { value: number };
      restingListBottomPad: number;
      restingComposerClearance: number;
      emptyHeight: number;
    };
    const bodyLayout = () => (mockBodyProps.mock.calls.at(-1)?.[0] as { layout: BodyLayout }).layout;
    const resting = bodyLayout();
    // Tests have no safe area, so the composer rests on the 10 pt minimum pad.
    const idleBottomPad = 10;

    const midway = openingFrames[FRAMES / 2];
    await rendersDuring(emitAll(openingFrames.slice(0, FRAMES / 2 + 1)));
    expect(bodyLayout()).toBe(resting);
    expect(resting.keyboardLift.value).toBe(midway.height - idleBottomPad);

    await rendersDuring(emitAll([...openingFrames.slice(FRAMES / 2 + 1), { state: OPEN, height: KEYBOARD_HEIGHT }]));
    const open = bodyLayout();
    expect(open.keyboardLift.value).toBe(KEYBOARD_HEIGHT - idleBottomPad);
    expect(open.restingListBottomPad).toBe(resting.restingListBottomPad);
    expect(open.restingComposerClearance).toBe(resting.restingComposerClearance);
    // The empty state is the one height that waits for the keyboard to settle.
    expect(open.emptyHeight).toBe(resting.emptyHeight - (KEYBOARD_HEIGHT - idleBottomPad));
  });

  it("does not render when the drawer opens or closes", async () => {
    await render(<HomeScreen />);

    const open = await rendersDuring([() => openDrawer()]);
    const close = await rendersDuring([() => closeDrawer()]);

    expect({ open, close }).toEqual({ open: 0, close: 0 });
  });
});
