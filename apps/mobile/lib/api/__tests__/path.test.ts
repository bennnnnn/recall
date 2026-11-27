/**
 * API paths (lib/api/path.ts): a value is one segment and can never climb out of its route.
 * A chat link's id `../chats` made `DELETE /chats/../chats?if_empty=true`, which Android sent
 * as DELETE /chats (pre-launch review B1, 2026-11-27).
 */
import { apiPath, isRefusedApiPath, withQuery } from "@/lib/api/path";

/** Where a URL parser (the URL standard, as OkHttp and NSURL resolve it) sends a path. */
function resolved(path: string): string {
  return new URL(path, "https://api.test").pathname;
}

describe("apiPath", () => {
  const ID = "6f1c2b9e-0d7a-4b8e-9c3f-1a2b3c4d5e01";

  it("leaves a server id as it is", () => {
    expect(apiPath`/chats/${ID}/messages`).toBe(`/chats/${ID}/messages`);
  });

  it.each([
    ["../chats", "/chats/..%2Fchats"],
    ["../../auth/me", "/chats/..%2F..%2Fauth%2Fme"],
    ["x?if_empty=false", "/chats/x%3Fif_empty%3Dfalse"],
    ["x#y", "/chats/x%23y"],
    ["..%2Fchats", "/chats/..%252Fchats"],
    ["a b", "/chats/a%20b"],
  ])("keeps %j one segment under its route", (value, path) => {
    const built = apiPath`/chats/${value}`;
    expect(built).toBe(path);
    expect(isRefusedApiPath(built)).toBe(false);
    expect(resolved(built).startsWith("/chats/")).toBe(true);
    expect(resolved(built).split("/")).toHaveLength(3);
  });

  it.each(["", ".", "..", "..."])("refuses %j, which would name another path", (value) => {
    expect(isRefusedApiPath(apiPath`/chats/${value}?if_empty=true`)).toBe(true);
  });

  it("encodes every value, a number too", () => {
    expect(apiPath`/chats/${ID}/messages/${"m/1"}/feedback`).toBe(`/chats/${ID}/messages/m%2F1/feedback`);
    expect(apiPath`/todos/${7}`).toBe("/todos/7");
  });

  it("is a plain path with no values", () => {
    expect(apiPath`/chats`).toBe("/chats");
    expect(isRefusedApiPath("/chats")).toBe(false);
  });
});

describe("withQuery", () => {
  it("encodes each value and leaves out null and undefined", () => {
    expect(withQuery("/link-preview", { url: "https://a.test/x?y=1&z=2" }))
      .toBe("/link-preview?url=https%3A%2F%2Fa.test%2Fx%3Fy%3D1%26z%3D2");
    expect(withQuery("/todos/page", { limit: 200, completed_days: undefined, cursor: null }))
      .toBe("/todos/page?limit=200");
    expect(withQuery("/chats/archived", { cursor: "a&b=c" })).toBe("/chats/archived?cursor=a%26b%3Dc");
  });

  it("adds no ? for an empty query", () => {
    expect(withQuery("/attachments", { q: undefined })).toBe("/attachments");
  });
});
