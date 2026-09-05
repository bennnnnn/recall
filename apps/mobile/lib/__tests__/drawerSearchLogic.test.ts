import {
  hasMoreDrawerSearchResults,
  isAbortError,
  isValidDrawerSearchQuery,
  mergeDrawerSearchResults,
} from "@/lib/drawerSearchLogic";
import type { SearchResult } from "@/lib/api";

it("detects abort errors with or without a DOMException global", () => {
  expect(isAbortError(new DOMException("Aborted", "AbortError"))).toBe(true);
  const err = new Error("Aborted");
  err.name = "AbortError";
  expect(isAbortError(err)).toBe(true);
  expect(isAbortError(new Error("network"))).toBe(false);
  const domException = globalThis.DOMException;
  Object.defineProperty(globalThis, "DOMException", { value: undefined, configurable: true });
  try {
    expect(isAbortError(err)).toBe(true);
    expect(isAbortError({ name: "something-else" })).toBe(false);
  } finally {
    Object.defineProperty(globalThis, "DOMException", { value: domException, configurable: true });
  }
});

it.each([
  ["  ", false], [" x ", false], [" hi ", true], ["😀", false], ["😀😀", true],
  ["😀".repeat(200), true], ["😀".repeat(201), false],
])("enforces code-point query bounds for %s", (query, valid) => {
  expect(isValidDrawerSearchQuery(query)).toBe(valid);
});

it("allows the last legal offset and stops after the total or an empty page", () => {
  expect(hasMoreDrawerSearchResults(10_000, 20_000, 20)).toBe(true);
  expect(hasMoreDrawerSearchResults(10_020, 20_000, 20)).toBe(false);
  expect(hasMoreDrawerSearchResults(3, 3, 2)).toBe(false);
  expect(hasMoreDrawerSearchResults(3, 10, 0)).toBe(false);
});

it("keeps separate title/message hits and updates an overlapping message without duplicating it", () => {
  const title: SearchResult = { match_type: "title", chat_id: "chat", message_id: null, chat_title: "Old", content: "Old", role: "title", created_at: "2026-09-04" };
  const message = { ...title, match_type: "message" as const, message_id: "message", role: "user" };
  const merged = mergeDrawerSearchResults([title, message], [{ ...message, chat_title: "New" }]);
  expect(merged).toHaveLength(2);
  expect(merged[0]).toBe(title);
  expect(merged[1].chat_title).toBe("New");
});
