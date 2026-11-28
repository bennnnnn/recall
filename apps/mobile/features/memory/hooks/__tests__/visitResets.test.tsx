// Review of #2621: Memory stays mounted across a blur and return now, so state a visit sets
// must end however the visit ended. A line saved while away still clears the composer (sent
// again, it saved twice), and Clear all's busy ends; only the toasts belong to the visit.
import { act, renderHook } from "@testing-library/react-native";

import { useClearAllMemories } from "@/features/memory/hooks/useClearAllMemories";
import { useSubmitInstruction } from "@/features/memory/hooks/useSubmitInstruction";
import { api } from "@/lib/api";

const mockFeedback = { success: jest.fn(), warning: jest.fn(), error: jest.fn() };
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => mockFeedback }));
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ token: "token" }) }));
jest.mock("@/lib/api", () => ({ api: { clearMemories: jest.fn() } }));
jest.mock("@/lib/haptics", () => ({ notifyDestructive: jest.fn() }));
jest.mock("@/ui/overlay/dialogs", () => ({ confirmDialog: jest.fn(async () => true) }));
jest.mock("@/features/memory/model/memoryDocumentsCache", () => ({ invalidateMemoryDocuments: jest.fn() }));
jest.mock("@/features/memory/model/memoryListCache", () => ({ setMemoriesCache: jest.fn() }));
jest.mock("@/lib/reportRecoverableError", () => ({ reportRecoverableError: jest.fn() }));

let current = true;
const isCurrentView = () => current;

beforeEach(() => {
  jest.clearAllMocks();
  current = true;
});

it("tells the composer a line saved while the page was away landed, and toasts nothing", async () => {
  let answer!: (value: unknown) => void;
  const instruct = jest.fn(() => new Promise((resolve) => { answer = resolve; }));
  const { result } = await renderHook(() => useSubmitInstruction(instruct as never, isCurrentView));
  let landed: boolean | undefined;
  await act(async () => {
    const pending = result.current("remember I'm vegetarian").then((value) => { landed = value; });
    current = false;
    answer({ ok: true, applied: 1, dropped: 0, reply: "Saved" });
    await pending;
  });
  expect(landed).toBe(true);
  expect(mockFeedback.success).not.toHaveBeenCalled();
});

it("ends Clear all's busy that finished while the page was away", async () => {
  let done!: () => void;
  (api.clearMemories as jest.Mock).mockReturnValue(new Promise<void>((resolve) => { done = resolve; }));
  const { result } = await renderHook(() => useClearAllMemories(isCurrentView));
  let clearing!: Promise<boolean>;
  await act(async () => { clearing = result.current.clearAll(); await Promise.resolve(); });
  expect(result.current.busy).toBe(true);
  await act(async () => { current = false; done(); await clearing; });
  expect(result.current.busy).toBe(false);
});
