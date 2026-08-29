import { parseApiErrorDetail, resolveChatError } from "@/lib/chatErrorMessage";

describe("chatErrorMessage", () => {
  const t = (key: string) => key;

  it("maps known error codes to i18n", () => {
    expect(resolveChatError({ message: "", code: "busy", isPro: false, t })).toEqual({
      kind: "busy",
      message: "chat.busy",
    });
    expect(
      resolveChatError({ message: "", code: "model_unavailable", isPro: false, t }),
    ).toEqual({
      kind: "model_unavailable",
      message: "chat.model_unavailable",
    });
  });

  it("parses FastAPI detail JSON", () => {
    expect(parseApiErrorDetail('{"detail":"Quota exceeded"}')).toBe("Quota exceeded");
    expect(
      resolveChatError({
        message: '{"detail":"You hit today\'s free limit."}',
        isPro: false,
        t,
      }),
    ).toEqual({
      kind: "quota",
      message: "chat.quota_exceeded_free",
    });
    expect(
      resolveChatError({
        message: "You've used up today's free limit.",
        code: "quota_exceeded",
        isPro: false,
        t,
      }).message,
    ).toBe("chat.quota_exceeded_free");
  });

  it("falls back for opaque API bodies", () => {
    expect(resolveChatError({ message: '{"detail":[]}', isPro: false, t })).toEqual({
      kind: "generic",
      message: "chat.error_generic",
    });
  });
});
