/**
 * The API slices build their paths with apiPath (lib/api/path.ts), and the deletes of
 * everything say they mean it. A chat link's id `../chats` made the empty-chat tidy send
 * DELETE /chats/../chats?if_empty=true, which Android sent as DELETE /chats (pre-launch
 * review B1, 2026-11-27).
 */
import { chatsApi } from "@/features/chat/api";
import { memoriesApi } from "@/features/memory/api";
import { todosApi } from "@/features/todos/api";
import { attachmentsApi } from "@/features/attachments/api";
import { request } from "@/lib/api/client";
import { isRefusedApiPath } from "@/lib/api/path";

jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 0 }));
jest.mock("@/lib/deviceTimezone", () => ({ getDeviceTimezone: () => "UTC" }));
jest.mock("@/features/attachments/model/downloadChatAttachment", () => ({
  removeCachedAttachmentFiles: jest.fn(async () => undefined),
}));
jest.mock("@/lib/api/client", () => ({ request: jest.fn(), requestRevalidated: jest.fn() }));

const mockRequest = request as jest.Mock;
const sentPath = () => String(mockRequest.mock.calls[0][0]);

/** Where Android's HTTP stack (and the URL standard) sends a path. */
const resolved = (path: string) => new URL(path, "https://api.test").pathname;

const CRAFTED = ["../chats", "../memories", "../../auth/me", "x/../../chats", "..%2Fchats"];

beforeEach(() => {
  mockRequest.mockReset().mockResolvedValue(undefined);
});

describe("a crafted id stays one segment under its route", () => {
  it.each(CRAFTED)("the empty-chat tidy for %j deletes no other route", async (id) => {
    await chatsApi.deleteChatIfEmpty("token", id);
    const [path, , init] = mockRequest.mock.calls[0];
    expect(init).toEqual({ method: "DELETE" });
    expect(resolved(String(path)).split("/")).toHaveLength(3);
    expect(resolved(String(path)).startsWith("/chats/")).toBe(true);
    expect(String(path).endsWith("?if_empty=true")).toBe(true);
  });

  it.each([
    ["a chat", () => chatsApi.deleteChat("token", "../chats"), "/chats/"],
    ["a memory", () => memoriesApi.deleteMemory("token", "../memories"), "/memories/"],
    ["a memory page", () => memoriesApi.deleteMemoryDocument("token", "../../chats"), "/memories/documents/"],
    ["a to-do", () => todosApi.deleteTodo("token", "../../memories"), "/todos/"],
    ["an attachment", () => attachmentsApi.deleteAttachment("token", "../chats"), "/attachments/"],
  ])("a delete of %s keeps the crafted id under its route", async (_name, call, route) => {
    await call();
    const path = resolved(sentPath());
    expect(path.startsWith(route)).toBe(true);
    expect(path.slice(route.length)).not.toContain("/");
  });

  it.each(["..", ".", ""])("names no request for the id %j: refused unsent", async (id) => {
    await chatsApi.deleteChatIfEmpty("token", id);
    expect(isRefusedApiPath(sentPath())).toBe(true);
  });
});

describe("the deletes of everything confirm", () => {
  it.each([
    ["every chat", () => chatsApi.deleteAllChats("token"), "/chats"],
    ["every memory", () => memoriesApi.clearMemories("token"), "/memories"],
  ])("deleting %s sends the confirmation", async (_name, call, path) => {
    await call();
    expect(mockRequest).toHaveBeenCalledWith(path, "token", {
      method: "DELETE",
      body: JSON.stringify({ confirm: "delete" }),
    });
  });
});
