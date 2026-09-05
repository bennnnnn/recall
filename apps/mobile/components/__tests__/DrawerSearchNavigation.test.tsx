import React from "react";
import { act, render } from "@testing-library/react-native";
import { ConversationList } from "@/components/ConversationList";
import { api, type SearchResult } from "@/lib/api";

let mockSession = 0;
let mockToken = "token";
let mockDrawerOpen = true;
const mockSetParams = jest.fn();
const mockCloseDrawer = jest.fn();
const mockClearHighlight = jest.fn();
let mockHeader: { onOpenSearch: () => void; onSearchChange: (value: string) => void };
let mockList: { onOpenChat: (id: string, messageId?: string | null) => void; onOpenSearchResult?: (id: string, messageId?: string | null) => void };
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/contexts/AuthContext", () => ({ useAuthToken: () => mockToken }));
jest.mock("@/contexts/DrawerContext", () => ({ useDrawer: () => ({ isOpen: mockDrawerOpen }) }));
jest.mock("expo-router", () => ({ useRouter: () => ({ setParams: mockSetParams }) }));
jest.mock("expo-linear-gradient", () => ({ LinearGradient: () => null }));
jest.mock("react-native-safe-area-context", () => ({ useSafeAreaInsets: () => ({ top: 0, bottom: 0 }) }));
jest.mock("@/lib/theme", () => ({ useTheme: () => ({ bg: "#ffffff" }), withAlpha: (color: string) => color }));
jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));
jest.mock("@/lib/api", () => ({ api: { search: jest.fn() } }));
jest.mock("@/lib/cache/galleryListCache", () => ({ prefetchGallery: jest.fn() }));
jest.mock("@/lib/drawer", () => ({ clearChatHighlightGlobal: () => mockClearHighlight(), closeDrawer: () => mockCloseDrawer(), getActiveChatIdGlobal: () => null, startNewChatGlobal: jest.fn() }));
jest.mock("@/hooks/useDrawerChatList", () => ({ useDrawerChatList: () => ({
  groups: { pinned: [], today: [], yesterday: [], last_7_days: [], this_month: [], older: [], archived: [] },
  allChats: [], load: jest.fn(), isSectionCollapsed: () => false,
}) }));
jest.mock("@/hooks/useChatBulkActions", () => ({ useChatBulkActions: () => ({}) }));
jest.mock("@/hooks/useChatMenuActions", () => ({ useChatMenuActions: () => ({}) }));
jest.mock("@/hooks/useDrawerChatSelection", () => ({ useDrawerChatSelection: () => ({ selectedIds: new Set(), selectedCount: 0 }) }));
jest.mock("@/hooks/useReminderBadgeCount", () => ({ useReminderBadgeCount: () => ({}) }));
jest.mock("@/components/ActionBanner", () => ({ ActionBanner: () => null }));
jest.mock("@/components/ChatActionsSheet", () => ({ ChatActionsSheet: () => null }));
jest.mock("@/components/ChatRenameSheet", () => ({ ChatRenameSheet: () => null }));
jest.mock("@/components/drawer/DrawerListHeader", () => ({ DrawerListHeader: () => null }));
jest.mock("@/components/drawer/DrawerFooter", () => ({ DrawerFooter: () => null }));
jest.mock("@/components/drawer/DrawerNavLinks", () => ({ DrawerNavLinks: () => null }));
jest.mock("@/components/drawer/DrawerSelectionBar", () => ({ DrawerSelectionBar: () => null }));
jest.mock("@/components/drawer/DrawerHeader", () => ({ DrawerHeader: (props: typeof mockHeader) => { mockHeader = props; return null; } }));
jest.mock("@/components/drawer/DrawerChatFlashList", () => ({ DrawerChatFlashList: (props: typeof mockList) => { mockList = props; return null; } }));
const result: SearchResult = { chat_id: "chat", message_id: "message", chat_title: "Chat", content: "match",
  match_type: "message", role: "user", created_at: "2026-01-01" };

beforeEach(() => {
  jest.clearAllMocks(); jest.useFakeTimers(); mockSession = 0; mockToken = "token"; mockDrawerOpen = true;
  jest.mocked(api.search).mockResolvedValue({ results: [result], total: 1 });
});
afterEach(() => { jest.useRealTimers(); });
async function search() {
  const view = await render(<ConversationList />);
  await act(async () => { mockHeader.onOpenSearch(); });
  await act(async () => { mockHeader.onSearchChange("hello"); });
  await act(async () => { jest.advanceTimersByTime(300); });
  return { view, press: mockList.onOpenSearchResult ?? mockList.onOpenChat };
}

it("rejects a retained result press immediately after account invalidation", async () => {
  const { press } = await search();
  mockSession++;
  await act(async () => { press("chat", "message"); });
  expect(mockSetParams).not.toHaveBeenCalled();
  expect(mockCloseDrawer).not.toHaveBeenCalled();
  expect(mockClearHighlight).not.toHaveBeenCalled();
});

it("rejects a retained result press after its query changes away and back", async () => {
  const { press } = await search();
  await act(async () => { mockHeader.onSearchChange("different"); });
  await act(async () => { mockHeader.onSearchChange("hello"); });
  await act(async () => { press("chat", "message"); });
  expect(mockSetParams).not.toHaveBeenCalled();
});

it("rejects a retained result press after the drawer closes and reopens", async () => {
  const { view, press } = await search();
  mockDrawerOpen = false;
  await view.rerender(<ConversationList />);
  mockDrawerOpen = true;
  await view.rerender(<ConversationList />);
  await act(async () => { press("chat", "message"); });
  expect(mockSetParams).not.toHaveBeenCalled();
});

it("preserves result presses across token refresh and passes the exact message target", async () => {
  const { view, press } = await search();
  mockToken = "refreshed";
  await view.rerender(<ConversationList />);
  await act(async () => { press("chat", "message"); });
  expect(mockSetParams).toHaveBeenCalledWith({ chatId: "chat", highlightMessage: "message" });
});

it("clears a previous message highlight when opening a title result", async () => {
  const { press } = await search();
  await act(async () => { press("chat", null); });
  expect(mockSetParams).toHaveBeenCalledWith({ chatId: "chat", highlightMessage: undefined });
  expect(mockClearHighlight).toHaveBeenCalledTimes(1);
});
