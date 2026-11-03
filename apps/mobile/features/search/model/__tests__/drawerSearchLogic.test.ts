import {
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

it("keeps separate title/message hits and updates an overlapping message without duplicating it", () => {
  const title: SearchResult = { match_type: "title", chat_id: "chat", message_id: null, chat_title: "Old", content: "Old", role: "title", created_at: "2026-09-04" };
  const message = { ...title, match_type: "message" as const, message_id: "message", role: "user" };
  const merged = mergeDrawerSearchResults([title, message], [{ ...message, chat_title: "New" }]);
  expect(merged).toHaveLength(2);
  expect(merged[0]).toBe(title);
  expect(merged[1].chat_title).toBe("New");
});

it("keeps a file hit apart from its message's own hit", () => {
  const message: SearchResult = { match_type: "message", chat_id: "chat", message_id: "message", chat_title: "T", content: "Here", role: "user", created_at: "2026-09-04" };
  const file = { ...message, match_type: "file" as const, content: "Study Guide.pdf" };
  expect(mergeDrawerSearchResults([message], [file])).toEqual([message, file]);
});
