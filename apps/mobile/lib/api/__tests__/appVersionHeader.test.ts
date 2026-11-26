/**
 * Every call names this build (`X-App-Version`, a chat socket's `app_version`), in the shape
 * the API reads (apps/api/app/core/client_version.py), so a reply an older build cannot draw
 * can be told apart by build.
 */
import { APP_VERSION_HEADER, appVersionHeaders, withAppVersion } from "@/lib/api/appVersionHeader";

jest.mock("@/lib/appVersion", () => ({ appVersion: () => ({ version: "1.2.0", build: "42", update: null }) }));

declare const __dirname: string;
const { readFileSync } = jest.requireActual<{
  readFileSync(path: string, encoding: "utf8"): string;
}>("node:fs");
const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");

it("names the version and its native build", () => {
  expect(appVersionHeaders()).toEqual({ "X-App-Version": "1.2.0+42" });
});

it("puts it on a chat socket's URL beside the request id", () => {
  expect(withAppVersion("wss://api.test/ws/chat?request_id=m1")).toBe(
    "wss://api.test/ws/chat?request_id=m1&app_version=1.2.0%2B42",
  );
});

it("uses the header and the rule the API reads", () => {
  const source = readFileSync(join(__dirname, "../../../../api/app/core/client_version.py"), "utf8");
  expect(source).toContain(`APP_VERSION_HEADER = "${APP_VERSION_HEADER}"`);
  expect(source).toContain('_APP_VERSION_QUERY = "app_version"');
  expect(source).toContain("_APP_VERSION_RE = re.compile(r\"^[0-9A-Za-z._+-]{1,32}$\")");
});
