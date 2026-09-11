import React from "react";
import { Text } from "react-native";
import { act, render, waitFor } from "@testing-library/react-native";

import { useMemoryActions } from "@/hooks/useMemoryActions";

import { api } from "@/lib/api";
import { fetchMemories, getCachedMemories, updateMemoriesCache } from "@/lib/cache/memoryListCache";

jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 1 }));

jest.mock("@/lib/api", () => ({
  api: {
    deleteMemorySection: jest.fn(),
    deleteMemory: jest.fn(),
    updateMemory: jest.fn(),
  },
}));

jest.mock("@/lib/cache/memoryListCache", () => ({
  fetchMemories: jest.fn(),
  getCachedMemories: jest.fn(),
  updateMemoriesCache: jest.fn(),
}));

const mockApi = api as unknown as {
  deleteMemorySection: jest.Mock;
  deleteMemory: jest.Mock;
  updateMemory: jest.Mock;
};
const mockFetch = fetchMemories as unknown as jest.Mock;
const mockCached = getCachedMemories as unknown as jest.Mock;

const TEA = {
  id: "m1",
  type: "fact",
  text: "Likes tea.",
  created_at: "2026-01-01T00:00:00Z",
} as never;
const COFFEE = {
  id: "m2",
  type: "fact",
  text: "Likes coffee.",
  created_at: "2026-01-01T00:00:00Z",
} as never;

// `renderHook` is not exported by @testing-library/react-native v14, so drive
// the hook through a probe component and capture its return value.
type Actions = ReturnType<typeof useMemoryActions>;
let current: Actions;

function Probe({ token }: { token: string | null }) {
  const result = useMemoryActions(token);
  React.useLayoutEffect(() => {
    current = result;
  }, [result]);
  return <Text>{result.memories.length}</Text>;
}

async function mount(token: string | null = "tok") {
  // React 19 does not flush the initial render synchronously here, so `current`
  // would still be unset (or a render behind) without an act-wrapped mount.
  await act(async () => {
    render(<Probe token={token} />);
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  let cached = [TEA, COFFEE];
  mockCached.mockImplementation(() => cached);
  jest.mocked(updateMemoriesCache).mockImplementation((update) => {
    cached = update(cached) as typeof cached;
    return cached;
  });
  mockFetch.mockImplementation(async () => cached);
});

describe("useMemoryActions", () => {
  it("removes the section optimistically and keeps it removed on success", async () => {
    mockApi.deleteMemorySection.mockResolvedValue(undefined);
    await mount();

    let ok: boolean | undefined;
    await act(async () => {
      ok = await current.deleteSection("fact");
    });

    expect(ok).toBe(true);
    expect(current.memories).toEqual([]);
  });

  it("rolls the section back when the delete fails", async () => {
    mockApi.deleteMemorySection.mockRejectedValue(new Error("boom"));
    await mount();

    let ok: boolean | undefined;
    await act(async () => {
      ok = await current.deleteSection("fact");
    });

    expect(ok).toBe(false);
    expect(current.memories).toEqual([TEA, COFFEE]);
  });

  it("drops one fact and leaves the rest on success", async () => {
    mockApi.deleteMemory.mockResolvedValue(undefined);
    await mount();

    await act(async () => {
      await current.deleteFact(TEA);
    });

    expect(current.memories).toEqual([COFFEE]);
  });

  it("reloads from the server when a fact delete fails, instead of trusting the snapshot", async () => {
    mockApi.deleteMemory.mockRejectedValue(new Error("404"));
    await mount();

    let ok: boolean | undefined;
    await act(async () => {
      ok = await current.deleteFact(TEA);
    });

    expect(ok).toBe(false);
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("tok", { force: true, afterPending: true });
    });
  });

  it("prefers the server copy of an edited memory over the optimistic draft", async () => {
    mockApi.updateMemory.mockResolvedValue({ ...TEA, text: "stamped by server" });
    await mount();

    let ok: boolean | undefined;
    await act(async () => {
      ok = await current.updateMemoryText("m1", "my draft");
    });

    expect(ok).toBe(true);
    expect(current.memories[0].text).toBe("stamped by server");
  });

  it("rolls an edit back when the update fails", async () => {
    mockApi.updateMemory.mockRejectedValue(new Error("boom"));
    await mount();

    let ok: boolean | undefined;
    await act(async () => {
      ok = await current.updateMemoryText("m1", "my draft");
    });

    expect(ok).toBe(false);
    expect(current.memories[0].text).toBe(TEA.text);
  });

  it("does nothing without a token", async () => {
    await mount(null);

    await act(async () => {
      expect(await current.deleteSection("fact")).toBe(false);
    });
    expect(mockApi.deleteMemorySection).not.toHaveBeenCalled();
  });
});
