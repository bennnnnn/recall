/**
 * Deleting the account says it means it: the API deletes nothing for a bearer token alone
 * (apps/api modules/account/api.py delete_me), so every delete the phone sends carries the
 * confirmation, spelled as the API reads it.
 */
import { ACCOUNT_DELETE_CONFIRMATION, accountApi } from "@/features/account/api";
import { request } from "@/lib/api/client";

jest.mock("@/lib/api/client", () => ({
  request: jest.fn(async () => undefined),
  requestRevalidated: jest.fn(),
  fetchExportText: jest.fn(),
}));

declare const __dirname: string;
const { readFileSync } = jest.requireActual<{
  readFileSync(path: string, encoding: "utf8"): string;
}>("node:fs");
const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");

function sentBody(): unknown {
  const init = jest.mocked(request).mock.calls.at(-1)?.[2] as { method: string; body: string };
  expect(init.method).toBe("DELETE");
  return JSON.parse(init.body);
}

it.each([
  [undefined, { confirm: "delete" }],
  ["apple-code", { confirm: "delete", apple_authorization_code: "apple-code" }],
])("sends the confirmation with every delete (Apple code %s)", async (code, body) => {
  await accountApi.deleteAccount("token", code);
  expect(sentBody()).toEqual(body);
});

it("spells the confirmation as the API reads it", () => {
  const source = readFileSync(join(__dirname, "../../../../api/app/models/schemas/auth.py"), "utf8");
  expect(source).toContain(`ACCOUNT_DELETE_CONFIRMATION = "${ACCOUNT_DELETE_CONFIRMATION}"`);
});
