import { INSTRUCT_TIMEOUT_MS, memoriesApi } from "@/features/memory/api";
import { instructFailure, STILL_SAVING_MS } from "@/features/memory/model/instructInFlight";
import { memoryFailureKey } from "@/features/memory/model/memoryFailure";
import { request } from "@/lib/api/client";

jest.mock("@/lib/api/client", () => ({ request: jest.fn(async () => ({})), requestRevalidated: jest.fn() }));

describe("a typed memory edit", () => {
  it("is waited for past the server's own budget, not the 30 s default", async () => {
    await memoriesApi.instructMemory("token", "keep lists short");
    expect(jest.mocked(request).mock.calls.at(-1)?.[4]).toBe(INSTRUCT_TIMEOUT_MS);
    expect(INSTRUCT_TIMEOUT_MS).toBeGreaterThan(30_000);
  });

  it("met by a busy memory soon after one went unanswered is that edit still saving", () => {
    const now = 1_000_000;
    expect(instructFailure("busy", now - 10_000, now)).toBe("saving");
    expect(memoryFailureKey("saving", "memory.instruct_failed")).toBe("memory.still_saving");
  });

  it.each([
    ["no edit went unanswered", "busy", null, "busy"],
    ["the unanswered one is long past", "busy", 1_000_000 - STILL_SAVING_MS - 1, "busy"],
    ["the failure is another", "off", 1_000_000 - 10, "off"],
  ] as const)("is told as it is when %s", (_label, failure, unansweredAt, expected) => {
    expect(instructFailure(failure, unansweredAt, 1_000_000)).toBe(expected);
  });
});
