/**
 * A typed memory edit's retry says "still saving" only after an edit from here was sent and
 * not answered in time: after one that never connected, a busy memory is another write.
 */
import { act, renderHook } from "@testing-library/react-native";

import fixture from "../../../../../../docs/fixtures/error_codes.json";
import { useMemoryInstruct } from "@/features/memory/hooks/useMemoryInstruct";
import { noteInstructAnswered } from "@/features/memory/model/instructInFlight";
import { api } from "@/lib/api";
import { abortError } from "@/lib/api/deadline";
import { ApiRequestError } from "@/lib/api/errorBody";

jest.mock("@/lib/api", () => ({ api: { instructMemory: jest.fn() } }));
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 1 }));
jest.mock("@/features/memory/model/memoryListCache", () => ({ invalidateMemoriesCache: jest.fn() }));

beforeEach(() => noteInstructAnswered());

const busy = () =>
  new ApiRequestError(fixture.memory_busy.status, JSON.stringify({ detail: fixture.memory_busy.detail }));

it.each([
  ["sent, and its wait ran out", abortError(), "saving"],
  ["never connected (offline)", new TypeError("Network request failed"), "busy"],
])("after an edit that %s, a busy memory is told as %s", async (_label, first, told) => {
  jest.mocked(api.instructMemory).mockRejectedValueOnce(first).mockRejectedValueOnce(busy());
  const { result } = await renderHook(() => useMemoryInstruct("token"));
  await act(async () => {
    await result.current("keep lists short");
  });
  let outcome: Awaited<ReturnType<typeof result.current>> | undefined;
  await act(async () => {
    outcome = await result.current("keep lists short");
  });
  expect(outcome).toEqual({ ok: false, failure: told });
});

it("knows its own unanswered edit from another memory screen, or after a remount", async () => {
  jest.mocked(api.instructMemory).mockRejectedValueOnce(abortError()).mockRejectedValueOnce(busy());
  const list = await renderHook(() => useMemoryInstruct("token"));
  await act(async () => {
    await list.result.current("keep lists short");
  });
  list.unmount();
  const page = await renderHook(() => useMemoryInstruct("token"));
  let outcome: Awaited<ReturnType<typeof page.result.current>> | undefined;
  await act(async () => {
    outcome = await page.result.current("keep lists short");
  });
  expect(outcome).toEqual({ ok: false, failure: "saving" });
});
