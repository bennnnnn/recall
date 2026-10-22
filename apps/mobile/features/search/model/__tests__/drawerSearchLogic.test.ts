import {
  hasMoreDrawerSearchResults,
  isValidDrawerSearchQuery,
  mergeDrawerSearchResults,
} from "@/features/search/model/drawerSearchLogic";
import type { SearchResult } from "@/lib/api";

it.each([
  ["  ", false], [" x ", false], [" hi ", false], [" hey ", true], ["😀😀", false], ["😀😀😀", true],
  ["😀".repeat(200), true], ["😀".repeat(201), false],
])("enforces code-point query bounds for %s", (query, valid) => {
  expect(isValidDrawerSearchQuery(query)).toBe(valid);
});

it("allows the last legal offset and stops when the server has no more or a page is empty", () => {
  expect(hasMoreDrawerSearchResults(10_000, true, 20)).toBe(true);
  expect(hasMoreDrawerSearchResults(10_020, true, 20)).toBe(false);
  expect(hasMoreDrawerSearchResults(3, false, 2)).toBe(false);
  expect(hasMoreDrawerSearchResults(3, true, 0)).toBe(false);
});

it("keeps separate title/message hits and updates an overlapping message without duplicating it", () => {
  const title: SearchResult = { match_type: "title", chat_id: "chat", message_id: null, chat_title: "Old", content: "Old", role: "title", created_at: "2026-09-04" };
  const message = { ...title, match_type: "message" as const, message_id: "message", role: "user" };
  const merged = mergeDrawerSearchResults([title, message], [{ ...message, chat_title: "New" }]);
  expect(merged).toHaveLength(2);
  expect(merged[0]).toBe(title);
  expect(merged[1].chat_title).toBe("New");
});
