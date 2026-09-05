import React from "react";
import { act, render } from "@testing-library/react-native";
import { useMemoryActions } from "@/hooks/useMemoryActions";
import { api, type Memory } from "@/lib/api";
import {
  getCachedMemories,
  invalidateMemoriesCache,
  setMemoriesCache,
} from "@/lib/cache/memoryListCache";

let mockSession = 0;
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => mockSession,
  requireTokenSession: jest.fn(),
}));
jest.mock("@/lib/api", () => ({ api: {
  listMemories: jest.fn(),
  deleteMemorySection: jest.fn(),
  deleteMemoryFact: jest.fn(),
  updateMemory: jest.fn(),
} }));

const mockApi = jest.mocked(api);
const original: Memory = {
  id: "fact", type: "fact", text: "Original fact.", confidence: null,
  created_at: "2026-01-01", updated_at: "2026-01-01",
};
const unrelated: Memory = { ...original, id: "profile", type: "profile", text: "Other section." };
let current: ReturnType<typeof useMemoryActions>;
function Probe() {
  const actions = useMemoryActions("token");
  React.useLayoutEffect(() => { current = actions; });
  return null;
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

beforeEach(() => {
  jest.resetAllMocks();
  mockSession++;
  invalidateMemoriesCache();
  setMemoriesCache([original, unrelated]);
});

it.each(["edit", "section delete"])("reconciles a failed %s after a pending GET replays the snapshot rollback", async (operation) => {
  const read = deferred<Memory[]>();
  const edit = deferred<Memory>();
  const deletion = deferred<void>();
  const authoritative = operation === "edit"
    ? [{ ...original, text: "Newer server fact." }, unrelated] : [unrelated];
  mockApi.listMemories.mockReturnValueOnce(read.promise).mockResolvedValueOnce(authoritative);
  mockApi.updateMemory.mockReturnValue(edit.promise);
  mockApi.deleteMemorySection.mockReturnValue(deletion.promise);
  await render(<Probe />);

  let loading!: Promise<void>;
  let mutation!: Promise<boolean>;
  await act(async () => {
    loading = current.load({ force: true });
    mutation = operation === "edit"
      ? current.updateMemoryText(original.id, "Local draft.")
      : current.deleteSection(original.type);
  });
  await act(async () => {
    if (operation === "edit") edit.reject(new Error("connection lost"));
    else deletion.reject(new Error("connection lost"));
    expect(await mutation).toBe(false);
  });
  expect(mockApi.listMemories).toHaveBeenCalledTimes(1);
  expect(current.memories).toContainEqual(original);

  await act(async () => {
    read.resolve(authoritative);
    await loading;
  });
  expect(current.memories).toEqual(authoritative);
  expect(getCachedMemories()).toEqual(authoritative);
  expect(mockApi.listMemories).toHaveBeenCalledTimes(2);
});
