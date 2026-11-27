/**
 * The API path lint (eslint.config.js, `recall/api-path`): a request's path is a literal or
 * comes from apiPath / withQuery (lib/api/path.ts). A chat link's id pasted into
 * `/chats/${chatId}?if_empty=true` made DELETE /chats on Android (pre-launch review B1).
 * Runs the real config.
 */
import { ROOT } from "@/lib/__tests__/support/sourceFiles";

type LintMessage = { line: number; ruleId: string | null };
type FlatLinter = { verify: (code: string, config: unknown, filename: string) => LintMessage[] };

// eslint-disable-next-line @typescript-eslint/no-require-imports -- eslint and its config are CommonJS, and the lib project has no @types/node
const { Linter } = require("eslint") as { Linter: new (options: { configType: "flat"; cwd: string }) => FlatLinter };
// eslint-disable-next-line @typescript-eslint/no-require-imports -- the config is CommonJS, as above
const config = require("../../eslint.config.js") as unknown;

const linter = new Linter({ configType: "flat", cwd: ROOT });

const HEADER = 'import { request, requestRaw, requestRevalidated, requestSse } from "@/lib/api/client";\n' +
  'import { apiPath, withQuery } from "@/lib/api/path";\n' +
  "declare const id: string;\ndeclare const token: string;\n";

function flagged(body: string, file = "features/chat/api.ts"): boolean {
  return linter
    .verify(HEADER + body, config, `${ROOT}/${file}`)
    .some((message) => message.ruleId === "recall/api-path");
}

describe("API path lint", () => {
  it.each([
    "export const a = request(`/chats/${id}?if_empty=true`, token);",
    "export const a = requestRaw(`/attachments/${id}/upload`, token);",
    "export const a = requestSse(`/chats/${id}/messages/stream`, token, {});",
    "export const a = requestRevalidated(`/todos/${id}`, token);",
    'export const a = request("/chats/" + id, token);',
    "export const path = `/chats/${id}/messages`;",
  ])("flags the raw path in %s", (body) => {
    expect(flagged(body)).toBe(true);
  });

  it("flags it in any feature, not only the API slices", () => {
    expect(flagged("export const a = request(`/memories/${id}`, token);", "features/memory/hooks/useX.ts")).toBe(true);
  });

  it.each([
    'export const a = request("/chats", token);',
    "export const a = request(apiPath`/chats/${id}`, token);",
    'export const a = request(withQuery(apiPath`/chats/${id}`, { if_empty: true }), token);',
    'export const a = request(withQuery("/link-preview", { url: id }), token);',
    // Not one of our paths: a cache file, a label.
    "export const file = `${id}.json`;",
  ])("allows %s", (body) => {
    expect(flagged(body)).toBe(false);
  });

  it("leaves tests their own paths", () => {
    expect(flagged("export const a = request(`/chats/${id}`, token);", "features/chat/__tests__/api.test.ts")).toBe(false);
  });
});
