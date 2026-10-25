import { loginWithApple, loginWithDev, loginWithGoogle } from "@/features/auth/api";
import { AccountExistsError, accountExistsProvider } from "@/features/auth/model/accountExists";
import { SignInLimitedError } from "@/features/auth/model/signInLimited";
import { ApiRequestError, fetchWithTimeout } from "@/lib/api/client";

jest.mock("@/lib/config", () => ({ getApiUrl: () => "https://api.test" }));
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => 0,
  requireTokenSession: jest.fn(),
  SessionChangedError: class extends Error {},
  getRefreshToken: jest.fn(),
  setTokenPair: jest.fn(),
}));
jest.mock("@/lib/api/client", () => ({
  ...jest.requireActual("@/lib/api/client"),
  apiUrl: (path: string) => `https://api.test${path}`,
  fetchWithTimeout: jest.fn(),
}));
jest.mock("@/lib/deviceSession", () => ({ deviceSessionFields: () => ({}) }));

const ACCOUNT_EXISTS = JSON.stringify({
  detail: {
    code: "account_exists",
    sign_in_with: "apple",
    message: "This email already has a Recall account.",
  },
});

function reply(status: number, body: string): Response {
  return { ok: status < 400, status, text: async () => body } as unknown as Response;
}

describe("accountExistsProvider", () => {
  it.each([
    [409, ACCOUNT_EXISTS, "apple"],
    [409, ACCOUNT_EXISTS.replace('"apple"', '"google"'), "google"],
    [409, ACCOUNT_EXISTS.replace('"apple"', '"dev"'), null],
    [409, JSON.stringify({ detail: "This email is taken" }), null],
    [409, JSON.stringify({ detail: { code: "other", sign_in_with: "apple" } }), null],
    [409, "not json", null],
    [401, ACCOUNT_EXISTS, null],
  ])("status %s body %s → %s", (status, body, expected) => {
    expect(accountExistsProvider(new ApiRequestError(status, body))).toBe(expected);
  });
});

describe("login errors", () => {
  it.each([
    ["Google", () => loginWithGoogle("id-token")],
    ["Apple", () => loginWithApple("id-token", null, "nonce")],
  ])("%s sign-in turns the 409 into AccountExistsError", async (_name, login) => {
    jest.mocked(fetchWithTimeout).mockResolvedValueOnce(reply(409, ACCOUNT_EXISTS));
    const error = await login().catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(AccountExistsError);
    expect((error as AccountExistsError).signInWith).toBe("apple");
  });

  it.each([
    ["Google", () => loginWithGoogle("id-token")],
    ["Apple", () => loginWithApple("id-token", null, "nonce")],
    ["dev", () => loginWithDev()],
  ])("%s sign-in turns a 429 into SignInLimitedError, not the server's English", async (_name, login) => {
    const limited = JSON.stringify({ detail: "Too many login attempts. Try again shortly." });
    jest.mocked(fetchWithTimeout).mockResolvedValueOnce(reply(429, limited));
    const error = await login().catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(SignInLimitedError);
    expect((error as Error).message).not.toContain("Too many");
  });

  it("keeps other failures as the server's words", async () => {
    jest.mocked(fetchWithTimeout).mockResolvedValueOnce(reply(401, '{"detail":"Invalid"}'));
    await expect(loginWithGoogle("id-token")).rejects.toThrow("Invalid");
  });
});

describe("sign-in deadline (NET-17)", () => {
  afterEach(() => jest.useRealTimers());

  it("gives up when the reply's body never finishes", async () => {
    jest.useFakeTimers();
    jest.mocked(fetchWithTimeout).mockResolvedValueOnce(
      { ok: true, status: 200, json: () => new Promise(() => undefined) } as unknown as Response,
    );
    const outcome = loginWithGoogle("id-token").catch((caught: unknown) => caught);
    await jest.advanceTimersByTimeAsync(15_000);
    await expect(outcome).resolves.toMatchObject({ message: expect.stringContaining("Could not reach") });
  });
});
