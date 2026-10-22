import { act, renderHook } from "@testing-library/react-native";

import { useSettingsProposal } from "@/hooks/useSettingsProposal";
import { onAppEvent } from "@/lib/appEvents";

const mockConfirm = jest.fn();
const mockMergeUser = jest.fn();
const mockSetPreference = jest.fn(async () => {});
const memoryChanged = jest.fn();
onAppEvent("memoryChanged", memoryChanged);

jest.mock("@/lib/api", () => ({
  api: { confirmSettingsProposal: (...args: unknown[]) => mockConfirm(...args) },
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "token-a", mergeUser: mockMergeUser }),
}));
jest.mock("@/contexts/AppearanceContext", () => ({
  useAppearance: () => ({ setPreference: mockSetPreference }),
}));
jest.mock("@/lib/cachedUser", () => ({ writeCachedUser: jest.fn(async () => {}) }));

beforeEach(() => {
  jest.clearAllMocks();
});

describe("useSettingsProposal", () => {
  it("re-reads the Memory pages after a memory card clears memory", async () => {
    mockConfirm.mockResolvedValue({
      user: { id: "u1", memory_enabled: true },
      appearance: null,
      applied: [{ field: "memory", value: "clear", label: "Delete everything saved" }],
    });
    const { result } = await renderHook(() =>
      useSettingsProposal({
        proposal_id: "m1",
        changes: [{ field: "memory", value: "clear", label: "Delete everything saved" }],
      }),
    );

    let ok = false;
    await act(async () => {
      ok = await result.current.confirm();
    });

    expect(ok).toBe(true);
    expect(mockConfirm).toHaveBeenCalledWith("token-a", "m1");
    // The memory caches follow the event; this hook no longer edits them (ARCH-10).
    expect(memoryChanged).toHaveBeenCalledTimes(1);
  });

  it("leaves memory caches alone for an appearance change", async () => {
    mockConfirm.mockResolvedValue({
      user: { id: "u1" },
      appearance: "dark",
      applied: [{ field: "appearance", value: "dark", label: "Dark" }],
    });
    const { result } = await renderHook(() =>
      useSettingsProposal({
        proposal_id: "a1",
        changes: [{ field: "appearance", value: "dark", label: "Dark" }],
      }),
    );
    await act(async () => {
      await result.current.confirm();
    });
    expect(mockSetPreference).toHaveBeenCalledWith("dark");
    expect(memoryChanged).not.toHaveBeenCalled();
  });
});
