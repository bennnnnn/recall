/**
 * Every call names this build (`X-App-Version`, a chat socket's `app_version`), in the shape
 * the API reads (apps/api/app/core/client_version.py), so a reply an older build cannot draw
 * can be told apart by build.
 */
import { APP_VERSION_HEADER, appVersionHeaders, nameThisBuild, withAppVersion } from "@/lib/api/appVersionHeader";

declare const __dirname: string;
const { readFileSync } = jest.requireActual<{
  readFileSync(path: string, encoding: "utf8"): string;
}>("node:fs");
const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");

it("names nothing until the build is named, then its version and native build", () => {
  expect(appVersionHeaders()).toEqual({});
  expect(withAppVersion("wss://api.test/ws/chat?request_id=m1")).toBe("wss://api.test/ws/chat?request_id=m1");
  nameThisBuild({ version: "1.2.0", build: "42" });
  expect(appVersionHeaders()).toEqual({ "X-App-Version": "1.2.0+42" });
});

it("never sends a malformed name", () => {
  nameThisBuild({ version: "1.2.0 beta", build: null });
  expect(appVersionHeaders()).toEqual({});
  nameThisBuild({ version: "1.2.0", build: "42" });
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
