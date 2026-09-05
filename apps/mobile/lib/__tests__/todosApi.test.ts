import { todosApi } from "@/lib/api/todos";
import { request } from "@/lib/api/client";
import type { Todo } from "@/lib/api/types";
jest.mock("@/lib/api/client", () => ({ request: jest.fn() }));
const page = Array.from({ length: 1000 }, (_, index) => ({ id: String(index) } as Todo));
const cursor = "00000000-0000-0000-0000-000000000999";
beforeEach(() => jest.resetAllMocks());

it("loads every page before returning the authoritative list", async () => {
  jest.mocked(request)
    .mockResolvedValueOnce({ items: page, next_cursor: cursor })
    .mockResolvedValueOnce({ items: [{ id: "last" }], next_cursor: null });
  const options = { signal: new AbortController().signal };
  expect(await todosApi.listTodos("token", options)).toHaveLength(1001);
  expect(request).toHaveBeenNthCalledWith(1, "/todos/page?limit=1000", "token", options);
  expect(request).toHaveBeenNthCalledWith(2, `/todos/page?limit=1000&cursor=${cursor}`, "token", options);
});

it("rejects a partial list when a later page fails", async () => {
  jest.mocked(request)
    .mockResolvedValueOnce({ items: page, next_cursor: cursor })
    .mockRejectedValueOnce(new Error("offline"));
  await expect(todosApi.listTodos("token")).rejects.toThrow("offline");
});

it("follows the cursor even when concurrent deletions leave an empty page", async () => {
  jest.mocked(request)
    .mockResolvedValueOnce({ items: [], next_cursor: cursor })
    .mockResolvedValueOnce({ items: [{ id: "remaining" }], next_cursor: null });
  await expect(todosApi.listTodos("token")).resolves.toEqual([{ id: "remaining" }]);
  expect(request).toHaveBeenCalledTimes(2);
});

it("stops on a terminal full page without an extra request", async () => {
  jest.mocked(request).mockResolvedValueOnce({ items: page, next_cursor: null });
  await expect(todosApi.listTodos("token")).resolves.toEqual(page);
  expect(request).toHaveBeenCalledTimes(1);
});

it("rejects a looping cursor before returning incomplete data", async () => {
  jest.mocked(request)
    .mockResolvedValueOnce({ items: [{ id: "first" }], next_cursor: cursor })
    .mockResolvedValueOnce({ items: [], next_cursor: "00000000-0000-0000-0000-000000001000" })
    .mockResolvedValueOnce({ items: [], next_cursor: cursor });
  await expect(todosApi.listTodos("token")).rejects.toThrow("Todo pagination did not advance");
  expect(request).toHaveBeenCalledTimes(3);
});

it("propagates cancellation from a later page without returning a partial list", async () => {
  const error = Object.assign(new Error("Aborted"), { name: "AbortError" });
  jest.mocked(request)
    .mockResolvedValueOnce({ items: page, next_cursor: cursor })
    .mockRejectedValueOnce(error);
  await expect(todosApi.listTodos("token")).rejects.toBe(error);
});

it("omits the unsupported project field from normal reminder creation", async () => {
  jest.mocked(request).mockResolvedValue({ id: "created" });
  await todosApi.createTodo("token", "Flight", "General", { dueAt: "2026-09-05T12:00:00Z" });
  const [path, token, init] = jest.mocked(request).mock.calls[0];
  expect(path).toBe("/todos");
  expect(token).toBe("token");
  expect(JSON.parse(init!.body as string)).toEqual({ content: "Flight", topic: "General", chat_id: null, due_at: "2026-09-05T12:00:00Z" });
});
