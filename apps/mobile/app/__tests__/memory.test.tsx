import { act, fireEvent, render } from "@testing-library/react-native";
import { Alert } from "react-native";
import MemoryScreen from "@/app/memory";

let mockSession = 1;
let mockToken: string | null = "token-a";
let mockFocused = true;
const mockLoad = jest.fn(async () => {});
const mockDeleteSection = jest.fn(async () => true);
const mockDeleteFact = jest.fn(async () => true);
const mockUpdate = jest.fn(async () => true);
const mockFeedback = { error: jest.fn() };
const mockRouter = { replace: jest.fn() };
const mockT = (key: string) => key;
const sample = { id: "m1", type: "profile", text: "First fact. Second fact. Third fact. Fourth fact.", confidence: 0.9, created_at: "2026-01-01", updated_at: "2026-01-01" };
let mockMemories = [sample];
let mockError = false;
let mockPending = new Set<string>();
let mockSheet: { onSave: () => void; onCancel: () => void };

jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/contexts/AuthContext", () => {
  const React = jest.requireActual("react");
  const Context = React.createContext(0);
  return { TestAuthProvider: Context.Provider, useAuth: () => {
    React.useContext(Context);
    return { token: mockToken };
  } };
});
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => mockFeedback }));
jest.mock("@/lib/reportRecoverableError", () => ({ reportRecoverableError: (...args: unknown[]) => mockFeedback.error(...args) }));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: mockT }) }));
jest.mock("react-native-safe-area-context", () => ({ useSafeAreaInsets: () => ({ bottom: 0 }) }));
jest.mock("@/lib/theme", () => ({ useTheme: () => ({}) }));
jest.mock("@/components/Icon", () => ({ Icon: () => null }));
jest.mock("@/components/SkeletonLoader", () => ({ SkeletonList: () => null }));
jest.mock("@/components/AppSheet", () => ({ AppSheet: ({ visible, children }: { visible: boolean; children: React.ReactNode }) => visible ? children : null }));
jest.mock("@/components/SheetFormHeader", () => ({ SheetFormHeader: (props: typeof mockSheet) => { mockSheet = props; return null; } }));
jest.mock("@/components/StateView", () => ({ StateView: ({ onRetry }: { onRetry?: () => void }) => {
  const { Text } = jest.requireActual("react-native");
  return <Text onPress={onRetry}>Retry</Text>;
} }));
jest.mock("expo-router", () => ({
  Redirect: () => null,
  useRouter: () => mockRouter,
  useFocusEffect: (effect: () => void | (() => void)) => {
    const React = jest.requireActual("react");
    const focused = mockFocused;
    React.useEffect(() => focused ? effect() : undefined, [effect, focused]);
  },
}));
jest.mock("@/lib/cache/memoryListCache", () => ({ getCachedMemories: () => mockMemories }));
jest.mock("@/hooks/useMemoryActions", () => ({ useMemoryActions: () => ({
  memories: mockMemories, loading: false, error: mockError, load: mockLoad,
  hasLoaded: mockHasLoaded, deleteSection: mockDeleteSection, deleteFact: mockDeleteFact,
  updateMemoryText: mockUpdate, pendingTypes: mockPending, isCurrentOwner: () => true,
}) }));
const mockHasLoaded = () => true;

beforeEach(() => {
  jest.clearAllMocks(); mockSession = 1; mockToken = "token-a"; mockFocused = true;
  mockMemories = [sample]; mockError = false; mockPending = new Set();
  mockUpdate.mockResolvedValue(true); mockDeleteSection.mockResolvedValue(true); mockDeleteFact.mockResolvedValue(true);
  jest.spyOn(Alert, "alert").mockImplementation(() => {});
});
afterEach(() => jest.restoreAllMocks());
function confirmDelete(): () => Promise<void> {
  return (Alert.alert as jest.Mock).mock.calls.at(-1)[2][1].onPress;
}
async function beginEdit(ui: Awaited<ReturnType<typeof render>>) {
  await fireEvent.press(ui.getByLabelText("memory.edit_section_a11y"));
  await fireEvent.changeText(ui.getByDisplayValue(sample.text), "Updated fact");
}

it("collapses a long fact list and expands it on request", async () => {
  const ui = await render(<MemoryScreen />);
  expect(ui.queryByText("Fourth fact.")).toBeNull();
  await fireEvent.press(ui.getByText("common.show_more"));
  expect(ui.getByText("Fourth fact.")).toBeTruthy();
});

it.each(["account", "blur", "blur-refocus", "unmount"])("ignores a retained delete confirmation after %s", async (change) => {
  const ui = await render(<MemoryScreen />);
  await fireEvent.press(ui.getByLabelText("memory.delete_section_a11y"));
  const confirm = confirmDelete();
  if (change === "account") mockSession++;
  if (change.startsWith("blur")) { mockFocused = false; await ui.rerender(<MemoryScreen />); }
  if (change === "blur-refocus") { mockFocused = true; await ui.rerender(<MemoryScreen />); }
  if (change === "unmount") await ui.unmount();
  await act(async () => { await confirm(); });
  expect(mockDeleteSection).not.toHaveBeenCalled();
  expect(mockFeedback.error).not.toHaveBeenCalled();
});

it("clears an account's editor before showing the next account", async () => {
  const ui = await render(<MemoryScreen />); await beginEdit(ui);
  mockSession++; mockToken = "token-b"; await ui.rerender(<MemoryScreen />);
  expect(ui.queryByDisplayValue("Updated fact")).toBeNull();
});

it("resets the editor on context-only account changes without rerendering the route element", async () => {
  const { TestAuthProvider } = jest.requireMock("@/contexts/AuthContext");
  const screen = <MemoryScreen />;
  const ui = await render(<TestAuthProvider value={1}>{screen}</TestAuthProvider>);
  await beginEdit(ui);
  mockSession++; mockToken = "token-b";
  await ui.rerender(<TestAuthProvider value={2}>{screen}</TestAuthProvider>);
  expect(ui.queryByDisplayValue("Updated fact")).toBeNull();
  await beginEdit(ui);
  expect(ui.getByDisplayValue("Updated fact")).toBeTruthy();
});

it("deduplicates Save callbacks invoked before React rerenders", async () => {
  let resolve!: (ok: boolean) => void;
  mockUpdate.mockReturnValue(new Promise<boolean>((done) => { resolve = done; }));
  const ui = await render(<MemoryScreen />); await beginEdit(ui);
  const save = mockSheet.onSave;
  await act(() => { save(); save(); });
  expect(mockUpdate).toHaveBeenCalledTimes(1);
  await act(async () => { resolve(true); });
});

it("does not report a failed save in a different account", async () => {
  let resolve!: (ok: boolean) => void;
  mockUpdate.mockReturnValue(new Promise<boolean>((done) => { resolve = done; }));
  const ui = await render(<MemoryScreen />); await beginEdit(ui);
  await act(() => { mockSheet.onSave(); });
  mockSession++; mockToken = "token-b"; await ui.rerender(<MemoryScreen />);
  await act(async () => { resolve(false); });
  expect(Alert.alert).not.toHaveBeenCalled();
});

it("preserves an edit through normal token refresh", async () => {
  const ui = await render(<MemoryScreen />); await beginEdit(ui);
  mockToken = "refreshed-token"; await ui.rerender(<MemoryScreen />);
  expect(ui.getByDisplayValue("Updated fact")).toBeTruthy();
});

it("edits a maximum-length stamped section without sending the server stamp back", async () => {
  const body = "x".repeat(4000);
  mockMemories = [{ ...sample, text: `As of 2026-09-04: ${body}` }];
  const ui = await render(<MemoryScreen />);
  await fireEvent.press(ui.getByLabelText("memory.edit_section_a11y"));
  expect(ui.getByDisplayValue(body)).toBeTruthy();
  await act(() => { mockSheet.onSave(); });
  expect(mockUpdate).toHaveBeenCalledWith(sample.id, body);
});

it("shows Retry alongside cached memories when refresh fails", async () => {
  mockError = true;
  const ui = await render(<MemoryScreen />);
  expect(ui.getByText("First fact.")).toBeTruthy();
  await fireEvent.press(ui.getByText("Retry"));
  expect(mockLoad).toHaveBeenLastCalledWith({ force: true });
});

it("disables mutations for a section with a pending write", async () => {
  mockPending.add("profile");
  const ui = await render(<MemoryScreen />);
  await fireEvent.press(ui.getByLabelText("memory.edit_section_a11y"));
  await fireEvent.press(ui.getByLabelText("memory.delete_section_a11y"));
  expect(ui.queryByDisplayValue(sample.text)).toBeNull();
  expect(Alert.alert).not.toHaveBeenCalled();
});
