/**
 * Request census: every request the phone sends through its one network boundary
 * (`fetch`, which only lib/api/client.ts calls for our API) and every socket it
 * opens, along an everyday session: cold start, chats opened, a turn, the drawer,
 * each screen, returns from the background, an expired token, a relaunch. Real
 * providers, hooks and caches; the server, the device stores and expo-router are
 * stand-ins. Each step has a ceiling: a step that sends more fails here.
 * `CENSUS=1 npx jest requestCensus` prints the requests.
 */
import type { ReactNode } from "react";

class MockExpoEmitter {
  addListener() { return { remove: () => {} }; }
  removeListener() {}
  removeAllListeners() {}
  emit() {}
  listenerCount() { return 0; }
}
(globalThis as unknown as { expo: unknown }).expo = {
  EventEmitter: MockExpoEmitter,
  NativeModule: MockExpoEmitter,
  SharedObject: MockExpoEmitter,
  SharedRef: MockExpoEmitter,
  modules: {},
  uuidv4: () => "uuid",
  uuidv5: () => "uuid",
  getViewConfig: () => null,
  reloadAppAsync: async () => {},
};

/** A native module stand-in: every member is a callable resolving to nothing; nothing is thenable. */
function mockNativeModule(name: string): unknown {
  const call = () => Promise.resolve(undefined);
  return new Proxy(call, {
    get(_target, prop) {
      if (prop === "then") return undefined;
      if (prop === "__esModule") return true;
      if (prop === Symbol.toPrimitive || prop === "toString") return () => name;
      return mockNativeModule(`${name}.${String(prop)}`);
    },
    apply: () => Promise.resolve(undefined),
    construct: () => mockNativeModule(`new ${name}`) as object,
  });
}

type Logged = { method: string; path: string; status: number };
const mockLog: Logged[] = [];
const mockSecure = new Map<string, string>();
const mockFiles = new Map<string, string>();
let mockParams: Record<string, string | undefined> = {};
const mockRouter = {
  push: jest.fn((href: unknown) => mockRouteTo(href)),
  replace: jest.fn((href: unknown) => mockRouteTo(href)),
  setParams: jest.fn((p: Record<string, string | undefined>) => {
    mockParams = { ...mockParams, ...p };
    setTimeout(() => void mockRerender?.(), 0);
  }),
  back: jest.fn(),
  canGoBack: () => true,
  dismissTo: jest.fn(),
  navigate: jest.fn((href: unknown) => mockRouteTo(href)),
};
let mockRerender: (() => Promise<void> | void) | null = null;
/** A move to the chat screen (the root route) sets its params; another route leaves them. */
function mockRouteTo(href: unknown) {
  setTimeout(() => void mockRerender?.(), 0);
  if (typeof href === "object" && href && "pathname" in href && href.pathname === "/") {
    mockParams = { ...(href as { params?: Record<string, string> }).params };
  } else if (typeof href === "string" && (href === "/" || href.startsWith("/?"))) {
    mockParams = Object.fromEntries(new URLSearchParams(href.slice(2)));
  }
}

jest.mock("expo-router", () => {
  const React = jest.requireActual("react");
  return {
    Redirect: () => null,
    Stack: Object.assign(({ children }: { children?: ReactNode }) => children ?? null, {
      Screen: () => null,
    }),
    useRouter: () => mockRouter,
    useNavigation: () => ({ setOptions: jest.fn(), addListener: () => () => {}, isFocused: () => true }),
    useLocalSearchParams: () => mockParams,
    useGlobalSearchParams: () => mockParams,
    usePathname: () => "/",
    useSegments: () => [],
    useFocusEffect: (effect: () => void | (() => void)) => React.useEffect(effect, [effect]),
    Link: ({ children }: { children?: ReactNode }) => children ?? null,
  };
});

jest.mock("expo-modules-core", () => {
  class EventEmitter { addListener() { return { remove: () => {} }; } removeAllListeners() {} emit() {} }
  const native = new Proxy({}, { get: (_t, k) => (k === "then" ? undefined : () => undefined) });
  return {
    EventEmitter,
    NativeModule: class {},
    SharedObject: class {},
    SharedRef: class {},
    requireOptionalNativeModule: () => null,
    requireNativeModule: () => native,
    requireNativeViewManager: () => () => null,
    registerWebModule: (m: unknown) => m,
    Platform: { OS: "ios" },
    PermissionStatus: { GRANTED: "granted", DENIED: "denied", UNDETERMINED: "undetermined" },
    createPermissionHook: () => () => [null, async () => ({}), async () => ({})],
    CodedError: class extends Error {},
    UnavailabilityError: class extends Error {},
    uuid: { v4: () => "uuid" },
  };
});

const mockNetState = { type: "wifi", isConnected: true, isInternetReachable: true, details: { ipAddress: "10.0.0.2" } };
jest.mock("@react-native-community/netinfo", () => ({
  __esModule: true,
  default: {
    configure: () => {},
    fetch: async () => mockNetState,
    refresh: async () => mockNetState,
    addEventListener: (listener: (s: unknown) => void) => {
      void Promise.resolve().then(() => listener(mockNetState));
      return () => {};
    },
  },
}));

jest.mock("expo-media-library", () => mockNativeModule("expo-media-library"));
jest.mock("expo-image-picker", () => mockNativeModule("expo-image-picker"));
jest.mock("expo-document-picker", () => mockNativeModule("expo-document-picker"));
jest.mock("expo-audio", () => mockNativeModule("expo-audio"));
jest.mock("expo-speech", () => mockNativeModule("expo-speech"));
jest.mock("expo-location", () => mockNativeModule("expo-location"));
jest.mock("expo-sharing", () => mockNativeModule("expo-sharing"));
jest.mock("expo-print", () => mockNativeModule("expo-print"));
jest.mock("expo-web-browser", () => mockNativeModule("expo-web-browser"));
jest.mock("expo-linking", () => mockNativeModule("expo-linking"));
jest.mock("expo-device", () => mockNativeModule("expo-device"));
jest.mock("expo-apple-authentication", () => mockNativeModule("expo-apple-authentication"));
jest.mock("@react-native-google-signin/google-signin", () => mockNativeModule("@react-native-google-signin/google-signin"));
jest.mock("react-native-purchases", () => mockNativeModule("react-native-purchases"));
jest.mock("react-native-webview", () => mockNativeModule("react-native-webview"));
jest.mock("expo-image-manipulator", () => mockNativeModule("expo-image-manipulator"));
jest.mock("expo-splash-screen", () => mockNativeModule("expo-splash-screen"));
jest.mock("expo-font", () => mockNativeModule("expo-font"));
jest.mock("expo-updates", () => mockNativeModule("expo-updates"));
jest.mock("react-native-webrtc", () => mockNativeModule("react-native-webrtc"));
jest.mock("react-native-vision-camera", () => mockNativeModule("react-native-vision-camera"));
jest.mock("react-native-vision-camera-mlkit", () => mockNativeModule("react-native-vision-camera-mlkit"));
jest.mock("react-native-vision-camera-worklets", () => mockNativeModule("react-native-vision-camera-worklets"));
jest.mock("react-native-nitro-image", () => mockNativeModule("react-native-nitro-image"));
jest.mock("react-native-nitro-modules", () => mockNativeModule("react-native-nitro-modules"));
jest.mock("@sentry/react-native", () => mockNativeModule("@sentry/react-native"));
jest.mock("@expo/dom-webview", () => mockNativeModule("@expo/dom-webview"));

jest.mock("react-native-gesture-handler/ReanimatedSwipeable", () => {
  const { View } = jest.requireActual("react-native");
  return { __esModule: true, default: View };
});

jest.mock("expo-constants", () => ({
  __esModule: true,
  default: {
    executionEnvironment: "standalone",
    appOwnership: null,
    expoConfig: { extra: { eas: { projectId: "proj" } }, version: "1.0.0" },
  },
  ExecutionEnvironment: { Bare: "bare", Standalone: "standalone", StoreClient: "storeClient" },
}));

jest.mock("expo-secure-store", () => ({
  getItemAsync: async (key: string) => mockSecure.get(key) ?? null,
  setItemAsync: async (key: string, value: string) => { mockSecure.set(key, value); },
  deleteItemAsync: async (key: string) => { mockSecure.delete(key); },
  AFTER_FIRST_UNLOCK: 0,
  AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY: 0,
}));

jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  documentDirectory: "file:///doc/",
  getInfoAsync: async (path: string) => ({ exists: mockFiles.has(path) }),
  readAsStringAsync: async (path: string) => {
    const v = mockFiles.get(path);
    if (v === undefined) throw new Error("missing");
    return v;
  },
  writeAsStringAsync: async (path: string, value: string) => { mockFiles.set(path, value); },
  deleteAsync: async (path: string) => { mockFiles.delete(path); },
  makeDirectoryAsync: async () => {},
  readDirectoryAsync: async () => [],
  copyAsync: async () => {},
  moveAsync: async () => {},
  EncodingType: { UTF8: "utf8", Base64: "base64" },
}));

jest.mock("expo-file-system", () => ({
  File: class { exists = false; textSync() { return ""; } },
  Paths: { document: "doc", cache: "cache" },
  Directory: class {},
}));

jest.mock("expo-notifications", () => ({
  getPermissionsAsync: async () => ({ status: "granted" }),
  requestPermissionsAsync: async () => ({ status: "granted" }),
  getExpoPushTokenAsync: async () => ({ data: "ExponentPushToken[abc]" }),
  getDevicePushTokenAsync: async () => ({ data: "apns-token", type: "ios" }),
  getLastNotificationResponseAsync: async () => null,
  addNotificationResponseReceivedListener: () => ({ remove: () => {} }),
  addNotificationReceivedListener: () => ({ remove: () => {} }),
  setNotificationHandler: () => {},
  getAllScheduledNotificationsAsync: async () => [],
  scheduleNotificationAsync: async () => "id",
  cancelScheduledNotificationAsync: async () => {},
  setNotificationChannelAsync: async () => {},
  AndroidImportance: { HIGH: 4, DEFAULT: 3 },
  SchedulableTriggerInputTypes: { DATE: "date" },
}));

const USER_ID = "u1";
const NOW = "2026-10-24T12:00:00Z";
const NOW_S = Date.parse(NOW) / 1000;
const accessToken = (exp: number, n = 0) => `h.${btoa(JSON.stringify({ sub: USER_ID, exp, n }))}.s`;
const USER = {
  id: USER_ID, email: "a@b.c", name: "Ann", avatar_url: null, default_model: "auto", plan: "free",
  features: [], enabled_models: null, ai_data_consent_at: NOW, response_tone: "", memory_enabled: true,
  push_notifications_enabled: true, push_reminders_enabled: true, reminder_lead_minutes: 0, locale: "en",
  // The device's own zone (lib/deviceTimezone): a profile in another is patched on start.
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone, location: null, location_enabled: false, custom_instructions: null, age: null,
  country: null, job: null, created_at: NOW,
};
const uuid = (kind: number, n: number) => `00000000-0000-4000-8${kind}00-${String(n).padStart(12, "0")}`;
const chatId = (n: number) => uuid(1, n);
const CHATS = Array.from({ length: 30 }, (_, i) => ({
  id: chatId(i), title: `Chat ${i}`, model: "auto", pinned: false, archived: false, created_at: NOW, updated_at: NOW,
}));
const fileContent = (n: number, type: string) =>
  `Summarize this file.\n[File: /attachments/${uuid(4, n)}/file]\n[File (${type})]`;
const MESSAGES = Array.from({ length: 30 }, (_, i) => ({
  id: uuid(2, i),
  role: i % 2 ? "assistant" : "user",
  // Three of the user's messages carry a file: two documents and a PDF.
  content: i === 4 ? fileContent(1, "text/plain") : i === 10 ? fileContent(2, "text/csv")
    : i === 16 ? fileContent(3, "application/pdf") : `Message ${i}`,
  model: null,
  created_at: NOW,
}));

/** A new chat's title lands after this many reads of it (the topic job runs after the reply). */
const TITLE_AFTER_READS = 2;
const titleReads = new Map<string, number>();
let refreshes = 0;
let created = 0;

function serverBody(method: string, path: string): unknown {
  const p = path.split("?")[0];
  if (p === "/auth/me") return USER;
  if (p === "/auth/refresh") {
    refreshes += 1;
    return {
      access_token: accessToken(Math.floor(Date.now() / 1000) + 3600, refreshes),
      refresh_token: `r${refreshes}`,
      user: USER,
    };
  }
  if (p === "/models") return [{ id: "free-chat", label: "Free", available: true, plan_access: "free" }];
  if (p === "/todos/page") return { items: [], next_cursor: null };
  if (p === "/chats/usage/today") return { date: "2026-10-24", tokens_used: 0, daily_limit: 100000 };
  if (p === "/chats" && method === "POST") {
    created += 1;
    return { ...CHATS[0], id: chatId(100 + created), title: null };
  }
  if (p === "/chats") {
    return {
      pinned: [], today: CHATS, yesterday: [], last_7_days: [], this_month: [], older: [], archived: [],
      next_cursor: null, archived_next_cursor: null,
    };
  }
  if (/^\/chats\/[^/]+\/messages$/.test(p)) return { messages: MESSAGES, has_more: false };
  if (/^\/chats\/[^/]+$/.test(p)) {
    const id = p.split("/")[2];
    const reads = (titleReads.get(id) ?? 0) + 1;
    titleReads.set(id, reads);
    return { ...CHATS[0], id, title: reads > TITLE_AFTER_READS ? "A new question" : null };
  }
  if (p === "/memories/documents") return { documents: [], scanning: false };
  if (p === "/memories") return [];
  if (p === "/attachments") return { items: [], next_cursor: null };
  if (p === "/auth/sessions") return { sessions: [] };
  if (/^\/attachments\/[^/]+\/url$/.test(p)) {
    return {
      id: p.split("/")[2], content_type: "text/plain", size_bytes: 100, url: "x", indexed: true,
      original_filename: "notes.txt", created_at: "2026-01-01T00:00:00Z",
    };
  }
  return {};
}

/** The lists the server answers with an ETag (`core/etag.py`): the drawer, to-dos, a chat's newest page. */
function revalidated(method: string, path: string): boolean {
  const p = path.split("?")[0];
  return method === "GET" && (
    path === "/chats" || p === "/todos/page" ||
    (/^\/chats\/[^/]+\/messages$/.test(p) && !/[?&](before|after|around)=/.test(path))
  );
}

type FakeSocket = {
  sent: string[];
  closed: boolean;
  onmessage: ((event: { data: string }) => void) | null;
};

let replies = 0;
/** The next reply's `done` says it changed the to-do list. */
let nextReplyChangesTodos = false;

function serverFrame(socket: FakeSocket, frame: object): void {
  if (!socket.closed) socket.onmessage?.({ data: JSON.stringify(frame) });
}

/** The server's side of a socket: a pong for a ping, and a streamed reply for a message. */
function answerFrame(socket: FakeSocket, raw: string): void {
  const frame = JSON.parse(raw) as { type?: string };
  if (frame.type === "ping") {
    setTimeout(() => serverFrame(socket, { type: "pong" }), 5);
    return;
  }
  if (frame.type !== "message") return;
  replies += 1;
  const id = uuid(3, replies);
  const todosChanged = nextReplyChangesTodos;
  nextReplyChangesTodos = false;
  setTimeout(() => serverFrame(socket, { type: "start" }), 50);
  for (let i = 0; i < 20; i++) {
    setTimeout(() => serverFrame(socket, { type: "token", content: `word${i} ` }), 100 + i * 20);
  }
  setTimeout(() => serverFrame(socket, { type: "stream_end" }), 600);
  setTimeout(() => serverFrame(socket, {
    type: "done", message_id: id, todos_changed: todosChanged,
    usage: { used_tokens: 10, daily_limit: 100000 },
  }), 700);
  setTimeout(() => serverFrame(socket, { type: "related_prompts", message_id: id, prompts: ["a?", "b?"] }), 900);
}

const mockAppStateListeners = new Set<(state: string) => void>();
const realFetch = globalThis.fetch;
const realWebSocket = globalThis.WebSocket;

function installServer(): void {
  globalThis.fetch = jest.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const path = String(url).replace(/^https?:\/\/[^/]+/, "");
    const method = (init?.method ?? "GET").toUpperCase();
    const body = JSON.stringify(serverBody(method, path));
    const etag = revalidated(method, path) ? `W/"${body.length}:${body.slice(-24)}"` : null;
    const headers = new Headers(init?.headers);
    if (etag && headers.get("If-None-Match") === etag) {
      mockLog.push({ method, path, status: 304 });
      return new Response(null, { status: 304, headers: { etag } });
    }
    mockLog.push({ method, path, status: 200 });
    return new Response(body, {
      status: 200,
      headers: { "content-type": "application/json", ...(etag ? { etag } : {}) },
    });
  }) as typeof fetch;
  class ServerSocket {
    readyState = 0;
    onopen: (() => void) | null = null;
    onmessage: ((event: { data: string }) => void) | null = null;
    onclose: ((event: { code: number }) => void) | null = null;
    onerror: (() => void) | null = null;
    sent: string[] = [];
    closed = false;
    constructor(url: string) {
      mockLog.push({ method: "WS", path: url.replace(/^wss?:\/\/[^/]+/, ""), status: 101 });
      setTimeout(() => {
        if (this.closed) return;
        this.readyState = 1;
        this.onopen?.();
      }, 20);
    }
    send(data: string) {
      this.sent.push(data);
      answerFrame(this, data);
    }
    close() {
      this.closed = true;
      this.readyState = 3;
    }
  }
  globalThis.WebSocket = ServerSocket as unknown as typeof WebSocket;
}

afterAll(() => {
  globalThis.fetch = realFetch;
  globalThis.WebSocket = realWebSocket;
});

type Step = { title: string; requests: string[] };
const steps: Step[] = [];
let mark = 0;
function step(title: string): void {
  steps.push({
    title,
    requests: mockLog.slice(mark).map((r) => `${r.method} ${r.path}${r.status === 304 ? " (304)" : ""}`),
  });
  mark = mockLog.length;
}

type Rtl = typeof import("@testing-library/react-native");
let rtl: Rtl;

/** Let `ms` pass on the fake clock, 50 ms at a time, with React's work flushed between. */
async function settle(ms = 50): Promise<void> {
  for (let elapsed = 0; elapsed < ms; elapsed += 50) {
    await rtl.act(async () => { await jest.advanceTimersByTimeAsync(50); });
  }
}

async function appState(state: "active" | "background" | "inactive"): Promise<void> {
  await rtl.act(async () => {
    for (const listener of [...mockAppStateListeners]) listener(state);
  });
}

type App = {
  ui: Awaited<ReturnType<Rtl["render"]>>;
  show: (route: string | null) => Promise<void>;
  rerender: () => Promise<void>;
};

/** A launch: no module state (every in-memory store empty); the device's files and keychain kept. */
async function launch(): Promise<App> {
  const clock = Date.now();
  jest.resetModules();
  mockAppStateListeners.clear();
  const { AppState } = await import("react-native");
  AppState.currentState = "active";
  AppState.addEventListener = ((_type: string, listener: (state: string) => void) => {
    mockAppStateListeners.add(listener);
    return { remove: () => mockAppStateListeners.delete(listener) };
  }) as typeof AppState.addEventListener;
  process.env.RNTL_SKIP_AUTO_CLEANUP = "true";
  rtl = await import("@testing-library/react-native");
  jest.setSystemTime(clock);
  const [{ AuthProvider }, { ModelsProvider }, { TodosProvider }, { NetworkProvider }, { PushNotificationBootstrap }] =
    await Promise.all([
      import("@/contexts/AuthContext"),
      import("@/contexts/ModelsContext"),
      import("@/features/todos/context/TodosContext"),
      import("@/contexts/NetworkContext"),
      import("@/features/todos/components/PushNotificationBootstrap"),
    ]);
  const ChatScreen = (await import("@/features/chat/screens/ChatScreen")).default;
  const routes: Record<string, () => ReactNode> = {
    memory: (await import("@/features/memory/screens/MemoryScreen")).default,
    todos: (await import("@/features/todos/screens/TodosScreen")).default,
    gallery: (await import("@/features/attachments/screens/GalleryScreen")).default,
    settings: (await import("@/features/account/screens/SettingsScreen")).default,
    usage: (await import("@/features/account/screens/UsageScreen")).default,
    models: (await import("@/features/account/screens/ModelsSettingsScreen")).default,
    about: (await import("@/features/account/screens/AboutScreen")).default,
    archived: (await import("@/features/account/screens/ArchivedChatsScreen")).default,
    dataControls: (await import("@/features/account/screens/DataControlsScreen")).default,
    help: (await import("@/features/account/screens/HelpScreen")).default,
    memorySettings: (await import("@/features/memory/screens/MemorySettingsScreen")).default,
    notifications: (await import("@/features/account/screens/NotificationsSettingsScreen")).default,
    preferences: (await import("@/features/account/screens/PreferencesSettingsScreen")).default,
    profile: (await import("@/features/account/screens/ProfileSettingsScreen")).default,
    security: (await import("@/features/account/screens/SecuritySettingsScreen")).default,
    voice: (await import("@/features/account/screens/VoiceSettingsScreen")).default,
  };
  let top: string | null = null;
  // The chat screen is the stack's root: it stays mounted under every screen pushed on it.
  const tree = () => {
    const Top = top ? routes[top] : null;
    return (
      <AuthProvider>
        <ModelsProvider>
          <TodosProvider>
            <NetworkProvider>
              <PushNotificationBootstrap />
              <ChatScreen />
              {Top ? <Top /> : null}
            </NetworkProvider>
          </TodosProvider>
        </ModelsProvider>
      </AuthProvider>
    );
  };
  const ui = await rtl.render(tree());
  const rerender = async () => { await ui.rerender(tree()); };
  mockRerender = rerender;
  return {
    ui,
    rerender,
    show: async (route) => {
      top = route;
      await rerender();
    },
  };
}

async function openChat(app: App, n: number, ms = 3000): Promise<void> {
  mockParams = { chatId: chatId(n) };
  await app.rerender();
  await settle(ms);
}

async function send(app: App, text: string): Promise<void> {
  await rtl.fireEvent.changeText(app.ui.getByTestId("chat-composer-input"), text);
  await settle(200);
  await rtl.fireEvent.press(app.ui.getByLabelText("chat.send_a11y"));
}

const SCREENS = [
  "memory", "todos", "gallery", "settings", "usage", "models", "about", "archived", "dataControls", "help",
  "memorySettings", "notifications", "preferences", "profile", "security", "voice",
];
/** A screen's read on opening it (none: it shows what the app already holds). */
const SCREEN_READS: Record<string, number> = {
  memory: 1, gallery: 1, usage: 1, archived: 1, memorySettings: 1, security: 1,
};

/** The most requests and sockets each step may send. */
const CEILINGS: Record<string, number> = {
  // /auth/me, the day's usage (free plan), to-dos, models, /health, the push token, the drawer.
  "cold start after sign-in": 7,
  // The newest page, each file's status (three), the socket.
  "open chat 1": 5,
  "open chat 2": 2,
  // The page this run kept is shown without a read; the socket reopens.
  "open chat 1 again within 20 s": 1,
  "send in chat 1": 0,
  "the reply finishes": 0,
  "20 s after the reply": 0,
  // The reply changed the to-do list: one read of it.
  "a reply that changes a to-do": 1,
  "open the drawer": 0,
  ...Object.fromEntries(SCREENS.map((name) => [`open ${name}`, SCREEN_READS[name] ?? 0])),
  ...Object.fromEntries(SCREENS.map((name) => [`leave ${name}`, 0])),
  "a minute in the background": 0,
  // To-dos and the open chat (ETag, 304), /health, the socket.
  "return after a minute": 4,
  // And the model list (older than 5 minutes).
  "return after 10 minutes": 5,
  // iOS goes inactive and back without leaving: nothing is read again.
  "Control Centre and back, 6 minutes on": 0,
  "50 minutes in the foreground": 0,
  // One refresh before the read, then the page and the socket.
  "open chat 2 after the token expired": 3,
  // One read per chat passed through, then the last one's socket.
  "switch chats 3 to 6 quickly": 5,
  "new chat": 0,
  // The chat, its socket, and the title read until the topic job has written it.
  "send in a new chat": 2 + TITLE_AFTER_READS + 1,
  "20 s after the new chat's reply": 0,
  // No push registration this time: the last one is under 12 hours old.
  "cold start again": 6,
  // The page; the files' statuses the first run settled come from disk.
  "open chat 1 after the relaunch": 2,
};

jest.setTimeout(120_000);

beforeEach(() => {
  jest.useFakeTimers();
  jest.setSystemTime(new Date(NOW));
  installServer();
});

it("keeps every step of an everyday session within its requests", async () => {
  mockSecure.set("recall_session_v1", JSON.stringify({ accessToken: accessToken(NOW_S + 3600), refreshToken: "r" }));
  mockFiles.set("file:///cache/cached-user.json", JSON.stringify({
    id: USER_ID, name: "Ann", avatar_url: null, plan: "free", ai_data_consent_at: NOW, locale: "en",
  }));
  let app = await launch();
  await settle(10_000);
  step("cold start after sign-in");

  await openChat(app, 1);
  step("open chat 1");
  await openChat(app, 2);
  step("open chat 2");
  await openChat(app, 1);
  step("open chat 1 again within 20 s");

  await send(app, "Hello there");
  await settle(400);
  step("send in chat 1");
  await settle(1500);
  step("the reply finishes");
  await settle(20_000);
  step("20 s after the reply");
  nextReplyChangesTodos = true;
  await send(app, "Remind me to call Sam at 5");
  await settle(3000);
  step("a reply that changes a to-do");

  const { openDrawer, closeDrawer } = await import("@/features/chat/drawer/drawer");
  await rtl.act(async () => { openDrawer(); });
  await settle(2000);
  await rtl.act(async () => { closeDrawer(); });
  await settle(500);
  step("open the drawer");

  for (const name of SCREENS) {
    await app.show(name);
    await settle(3000);
    step(`open ${name}`);
    await app.show(null);
    await settle(500);
    step(`leave ${name}`);
  }

  await appState("background");
  await settle(60_000);
  step("a minute in the background");
  await appState("active");
  await settle(3000);
  step("return after a minute");
  await appState("background");
  await settle(10 * 60_000);
  await appState("active");
  await settle(3000);
  step("return after 10 minutes");
  await settle(6 * 60_000);
  await appState("inactive");
  await settle(1000);
  await appState("active");
  await settle(3000);
  step("Control Centre and back, 6 minutes on");

  await settle(50 * 60_000);
  step("50 minutes in the foreground");
  await openChat(app, 2);
  step("open chat 2 after the token expired");

  for (const n of [3, 4, 5, 6]) {
    mockParams = { chatId: chatId(n) };
    await app.rerender();
    await settle(50);
  }
  await settle(3000);
  step("switch chats 3 to 6 quickly");

  mockParams = {};
  await app.rerender();
  await settle(1000);
  step("new chat");
  await send(app, "A new question");
  await settle(10_000);
  step("send in a new chat");
  await settle(20_000);
  step("20 s after the new chat's reply");

  app.ui.unmount();
  await settle(100);
  mark = mockLog.length;
  mockParams = {};
  app = await launch();
  await settle(10_000);
  step("cold start again");
  await openChat(app, 1);
  step("open chat 1 after the relaunch");

  if (process.env.CENSUS) {
    console.log(steps.map((s) => `${s.title} (${s.requests.length})\n${s.requests.map((r) => `  ${r}`).join("\n")}`)
      .join("\n"));
  }
  const over = steps
    .filter((s) => s.requests.length > (CEILINGS[s.title] ?? 0))
    .map((s) => `${s.title}: ${s.requests.length} > ${CEILINGS[s.title] ?? 0}\n  ${s.requests.join("\n  ")}`);
  expect(over).toEqual([]);
  expect(steps.map((s) => s.title).sort()).toEqual(Object.keys(CEILINGS).sort());
});
