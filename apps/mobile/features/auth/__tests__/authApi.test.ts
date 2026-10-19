import { loginWithApple, loginWithGoogle } from "@/features/auth/api";
import { AccountExistsError, accountExistsProvider } from "@/features/auth/model/accountExists";
import { fetchWithTimeout } from "@/lib/api/client";

jest.mock("@/lib/api/client", () => ({
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
    expect(accountExistsProvider(status, body)).toBe(expected);
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

  it("keeps other failures as the server's text", async () => {
    jest.mocked(fetchWithTimeout).mockResolvedValueOnce(reply(401, '{"detail":"Invalid"}'));
    await expect(loginWithGoogle("id-token")).rejects.toThrow('{"detail":"Invalid"}');
  });
});
