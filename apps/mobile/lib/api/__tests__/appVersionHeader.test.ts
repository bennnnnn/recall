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

it("uses the header the API reads, and names a build only when the API's rule takes it", () => {
  const source = readFileSync(join(__dirname, "../../../../api/app/core/client_version.py"), "utf8");
  expect(source).toContain(`APP_VERSION_HEADER = "${APP_VERSION_HEADER}"`);
  expect(source).toContain('_APP_VERSION_QUERY = "app_version"');
  const apiRule = new RegExp(source.match(/_APP_VERSION_RE = re\.compile\(r"([^"]+)"\)/)?.[1] ?? "(?!)");
  const builds: [string, string | null][] = [
    ["1.0.0", "42"], ["1.2.3", null], ["1.0.0-beta.1", "7"], ["1.0.0", "4 2"], ["1.0.0 beta", null],
    ["1".repeat(33), null], ["1".repeat(29), "42"], ["1.0.0/2", null], ["1.0.0", "42\nforged"],
  ];
  for (const [version, build] of builds) {
    nameThisBuild({ version, build });
    const name = build ? `${version}+${build}` : version;
    expect([name, Boolean(appVersionHeaders()[APP_VERSION_HEADER])]).toEqual([name, apiRule.test(name)]);
  }
  nameThisBuild({ version: "1.2.0", build: "42" });
});
