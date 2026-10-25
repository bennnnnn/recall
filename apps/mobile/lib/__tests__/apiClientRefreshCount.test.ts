/**
 * How many times the phone asks /auth/refresh when many requests meet a refused
 * token at once: the server rotates the refresh token on each one, so a refresh
 * that was not needed is load at the worst moment and one more rotation to lose.
 */
import { authorizeNativeTransfer, request, setTokenRefreshHandler, setUnauthorizedHandler } from "@/lib/api/client";

jest.mock("@/lib/config", () => ({ getApiUrl: () => "http://test.local" }));

let mockRefreshToken = "r0";
/** Each test is a sign-in of its own. */
let mockGeneration = 0;
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => mockGeneration,
  requireTokenSession: () => {},
  SessionChangedError: class extends Error {},
  getRefreshToken: async () => mockRefreshToken,
  setTokenPair: async (_access: string, refresh: string) => {
    mockRefreshToken = refresh;
    return true;
  },
}));

const jwt = (expSeconds: number, n: number) => `h.${btoa(JSON.stringify({ exp: expSeconds, n }))}.s`;
const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

type Server = {
  refreshes: number;
  signedOut: number;
  /** Tokens the server takes; a refresh adds the one it issues. */
  valid: Set<string>;
  /** The session is revoked: refresh answers 401. */
  revoked: boolean;
};

/** A server that answers each request after `latency(n)` ms and a refresh after 80 ms. */
function serve(latency: (n: number) => number): Server {
  const server: Server = { refreshes: 0, signedOut: 0, valid: new Set(), revoked: false };
  let n = 0;
  setUnauthorizedHandler(() => { server.signedOut += 1; });
  globalThis.fetch = jest.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    if (String(url).endsWith("/auth/refresh")) {
      server.refreshes += 1;
      await wait(80);
      if (server.revoked) return new Response("", { status: 401 });
      const token = jwt(Date.now() / 1000 + 3600, server.refreshes);
      server.valid.add(token);
      return new Response(JSON.stringify({ access_token: token, refresh_token: `r${server.refreshes}` }));
    }
    const token = (init?.headers as Record<string, string>).Authorization?.slice("Bearer ".length) ?? "";
    await wait(latency(n++));
    return new Response(server.valid.has(token) ? "{}" : "", { status: server.valid.has(token) ? 200 : 401 });
  }) as typeof fetch;
  return server;
}

beforeEach(() => {
  jest.useFakeTimers();
  mockGeneration += 1;
  mockRefreshToken = "r0";
  setTokenRefreshHandler(null);
});

afterEach(() => {
  jest.useRealTimers();
});

it("refreshes once when six requests meet a refused token and their 401s land 1.5 s apart", async () => {
  // The phone's clock is behind the server's: the token looks good here, the server refuses it.
  const server = serve((n) => [20, 60, 150, 400, 800, 1500][n] ?? 30);
  const token = jwt(Date.now() / 1000 + 600, 0);
  const all = Promise.allSettled(["/a", "/b", "/c", "/d", "/e", "/f"].map((path) => request(path, token)));
  await jest.advanceTimersByTimeAsync(5_000);
  expect((await all).map((result) => result.status)).toEqual(Array(6).fill("fulfilled"));
  expect(server.refreshes).toBe(1);
  expect(server.signedOut).toBe(0);
});

it("refreshes once more, then signs out, when the server refuses the refreshed token too", async () => {
  const server = serve(() => 20);
  const refused = jwt(Date.now() / 1000 + 600, 0);
  const first = request("/a", refused).catch(() => null);
  await jest.advanceTimersByTimeAsync(1_000);
  await first;
  expect(server.refreshes).toBe(1);
  // Signed out everywhere from another device: every token and the refresh are refused.
  server.valid.clear();
  server.revoked = true;
  const late = request("/b", refused).catch((error: unknown) => error);
  await jest.advanceTimersByTimeAsync(2_000);
  await late;
  expect(server.refreshes).toBe(2);
  expect(server.signedOut).toBe(1);
});

it("downloads with the refreshed token when a native transfer's 401 lands after a refresh", async () => {
  const server = serve(() => 20);
  const token = jwt(Date.now() / 1000 + 600, 0);
  const json = request("/a", token);
  await jest.advanceTimersByTimeAsync(1_000);
  await json;
  const sent: string[] = [];
  const status = await authorizeNativeTransfer(token, async (headers) => {
    sent.push(headers.Authorization);
    return server.valid.has(headers.Authorization.slice("Bearer ".length)) ? 200 : 401;
  });
  expect(status).toBe(200);
  expect(sent).toHaveLength(2);
  expect(server.refreshes).toBe(1);
});
