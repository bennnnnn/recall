import { readServerAuthCode } from "@/lib/google-integration-auth-code";

describe("readServerAuthCode", () => {
  it("returns trimmed code when present", () => {
    expect(readServerAuthCode({ data: { serverAuthCode: "abc123" } })).toBe("abc123");
  });

  it("returns null for empty or missing code", () => {
    expect(readServerAuthCode(null)).toBeNull();
    expect(readServerAuthCode({ data: { serverAuthCode: "  " } })).toBeNull();
    expect(readServerAuthCode({ data: {} })).toBeNull();
  });
});
