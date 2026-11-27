/**
 * A phone clock set an hour off judges token expiry on the server's clock (H9, 2026-11-27):
 * an hour fast refreshed before every request until the refresh limit locked the user out.
 */
import { accessTokenNeedsRefresh, request, setTokenRefreshHandler, setUnauthorizedHandler } from "@/lib/api/client";
import { noteServerDateHeader, noteServerTime, resetServerClockForTest } from "@/lib/api/serverClock";

jest.mock("@/lib/config", () => ({ getApiUrl: () => "http://test.local" }));

const mockSetTokenPair = jest.fn();
let mockSessionGeneration = 0;
let signIns = 0;

jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => mockSessionGeneration,
  requireTokenSession: jest.fn(),
  SessionChangedError: class extends Error {},
  getRefreshToken: jest.fn(async () => "refresh-token"),
  setTokenPair: (...args: unknown[]) => mockSetTokenPair(...args),
}));

const mockFetch = jest.fn();
globalThis.fetch = mockFetch as unknown as typeof fetch;

const HOUR_MS = 60 * 60_000;

function jwt(claims: Record<string, number>): string {
  const encode = (value: unknown) =>
    btoa(JSON.stringify(value)).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
  return `${encode({ alg: "HS256", typ: "JWT" })}.${encode({ sub: "u1", ...claims })}.signature`;
}

/** A token the server issued at `serverMs`, good for an hour. */
function issuedAt(serverMs: number, withIat = true): string {
  const iat = Math.floor(serverMs / 1000);
  return jwt(withIat ? { iat, exp: iat + 3600 } : { exp: iat + 3600 });
}

function answer(body: unknown, serverMs: number | null, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name: string) => (name === "date" && serverMs !== null ? new Date(serverMs).toUTCString() : null) },
    json: async () => body,
    text: async () => JSON.stringify(body),
  };
}

const refreshCalls = () => mockFetch.mock.calls.filter(([url]) => String(url).endsWith("/auth/refresh")).length;

beforeEach(() => {
  jest.clearAllMocks();
  jest.restoreAllMocks();
  resetServerClockForTest();
  mockSessionGeneration = (signIns += 100);
  mockSetTokenPair.mockResolvedValue(true);
  setUnauthorizedHandler(null);
  setTokenRefreshHandler(null);
});

describe.each([
  ["1 hour fast", HOUR_MS],
  ["1 hour slow", -HOUR_MS],
])("a phone clock %s", (_label, phoneAhead) => {
  const serverNowMs = 1_800_000_000_000;
  const phoneNowMs = serverNowMs + phoneAhead;

  it("judges expiry on the server's clock once an answer says what time it is", () => {
    const fresh = issuedAt(serverNowMs - 10 * 60_000);
    // Expired ten minutes ago: an hour-slow phone thought it had fifty minutes left.
    const expired = issuedAt(serverNowMs - 70 * 60_000);
    jest.spyOn(Date, "now").mockReturnValue(phoneNowMs);
    noteServerDateHeader(new Date(serverNowMs).toUTCString());
    expect(accessTokenNeedsRefresh(fresh)).toBe(false);
    expect(accessTokenNeedsRefresh(expired)).toBe(true);
  });

  it("takes the offset from a new token's iat as well", () => {
    jest.spyOn(Date, "now").mockReturnValue(phoneNowMs);
    noteServerTime(serverNowMs);
    expect(accessTokenNeedsRefresh(issuedAt(serverNowMs))).toBe(false);
  });
});

it.each([
  ["the Date header", true, false],
  ["the new token's iat", false, true],
])("an hour-fast phone learns the server's time from %s: one refresh, then none", async (_label, dateHeader, iat) => {
  const serverStart = 1_800_000_000_000;
  let elapsed = 0;
  jest.spyOn(Date, "now").mockImplementation(() => serverStart + HOUR_MS + elapsed);
  const stored = issuedAt(serverStart - 5 * 60_000);
  const fresh = issuedAt(serverStart, iat);
  mockFetch.mockImplementation(async (url: string) => {
    const date = dateHeader ? serverStart + elapsed : null;
    return url.endsWith("/auth/refresh")
      ? answer({ access_token: fresh, refresh_token: "r2" }, date)
      : answer({ ok: true }, date);
  });

  // Before any answer the phone's clock is all there is: the stored token looks expired.
  await request("/home", stored);
  expect(refreshCalls()).toBe(1);
  // Judged on the server's clock now, not held back by the back-off.
  expect(accessTokenNeedsRefresh(fresh)).toBe(false);
  // Twenty minutes of requests, two minutes apart: well past any back-off, inside the token's hour.
  for (let i = 0; i < 10; i += 1) {
    elapsed += 2 * 60_000;
    await request("/home", fresh);
  }
  expect(refreshCalls()).toBe(1);
});

it("a clock no answer corrects never loops: refreshes back off", async () => {
  // No Date header, no iat: the phone cannot learn the server's time.
  const serverNowMs = 1_800_000_000_000;
  let phoneNow = serverNowMs + 2 * HOUR_MS;
  jest.spyOn(Date, "now").mockImplementation(() => phoneNow);
  let issued = 0;
  mockFetch.mockImplementation(async (url: string) =>
    url.endsWith("/auth/refresh")
      ? answer({ access_token: issuedAt(serverNowMs + (issued += 1), false), refresh_token: "r" }, null)
      : answer({ ok: true }, null));

  const stored = issuedAt(serverNowMs - 5 * 60_000, false);
  for (let i = 0; i < 30; i += 1) await request("/home", stored);
  expect(refreshCalls()).toBe(1);

  // A minute on, the clock may ask again once, and then waits twice as long.
  phoneNow += 61_000;
  for (let i = 0; i < 30; i += 1) await request("/home", stored);
  expect(refreshCalls()).toBe(2);
  phoneNow += 61_000;
  for (let i = 0; i < 30; i += 1) await request("/home", stored);
  expect(refreshCalls()).toBe(2);
});

it("a token held back by a doubtful clock still refreshes once on a 401", async () => {
  const serverNowMs = 1_800_000_000_000;
  jest.spyOn(Date, "now").mockReturnValue(serverNowMs + 2 * HOUR_MS);
  const unauthorized = jest.fn();
  setUnauthorizedHandler(unauthorized);
  let homeCalls = 0;
  mockFetch.mockImplementation(async (url: string) => {
    if (url.endsWith("/auth/refresh")) {
      return answer({ access_token: issuedAt(serverNowMs, false), refresh_token: "r" }, null);
    }
    homeCalls += 1;
    // The second request's token is refused once: it must refresh, not sign out.
    return homeCalls === 2 ? answer({ detail: "expired" }, null, 401) : answer({ ok: true }, null);
  });
  const stored = issuedAt(serverNowMs - 5 * 60_000, false);
  await request("/home", stored);
  await request("/home", stored);
  expect(unauthorized).not.toHaveBeenCalled();
  expect(refreshCalls()).toBe(2);
});
