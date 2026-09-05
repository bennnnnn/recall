import { todosApi } from "@/lib/api/todos";
import { request } from "@/lib/api/client";
import type { Todo } from "@/lib/api/types";
jest.mock("@/lib/api/client", () => ({ request: jest.fn() }));
const page = Array.from({ length: 1000 }, (_, index) => ({ id: String(index) } as Todo));
beforeEach(() => jest.resetAllMocks());

it("loads every page before returning the authoritative list", async () => {
  jest.mocked(request).mockResolvedValueOnce(page).mockResolvedValueOnce([{ id: "last" }]);
  expect(await todosApi.listTodos("token")).toHaveLength(1001);
  const [path, token] = jest.mocked(request).mock.calls[1];
  const url = new URL(path, "https://recall.test");
  expect(url.searchParams.get("offset")).toBe("1000");
  expect(url.searchParams.get("limit")).toBe("1000");
  expect(token).toBe("token");
});

it("rejects a partial list when a later page fails", async () => {
  jest.mocked(request).mockResolvedValueOnce(page).mockRejectedValueOnce(new Error("offline"));
  await expect(todosApi.listTodos("token")).rejects.toThrow("offline");
});

it("omits the unsupported project field from normal reminder creation", async () => {
  jest.mocked(request).mockResolvedValue({ id: "created" });
  await todosApi.createTodo("token", "Flight", "General", { dueAt: "2026-09-05T12:00:00Z" });
  const [path, token, init] = jest.mocked(request).mock.calls[0];
  expect(path).toBe("/todos");
  expect(token).toBe("token");
  expect(JSON.parse(init!.body as string)).toEqual({ content: "Flight", topic: "General", chat_id: null, due_at: "2026-09-05T12:00:00Z" });
});
