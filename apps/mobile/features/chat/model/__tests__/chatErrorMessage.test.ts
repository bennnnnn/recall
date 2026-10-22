import { resolveChatError } from "@/features/chat/model/errorMessage";

describe("chatErrorMessage", () => {
  const t = (key: string) => key;

  it("maps known error codes to i18n", () => {
    expect(resolveChatError({ message: "", code: "busy", isPaid: false, t })).toEqual({
      kind: "busy",
      message: "chat.busy",
    });
    expect(
      resolveChatError({ message: "", code: "model_unavailable", isPaid: false, t }),
    ).toEqual({
      kind: "model_unavailable",
      message: "chat.model_unavailable",
    });
  });

  it("distinguishes an unsaved send from an active reply's busy notice", () => {
    expect(resolveChatError({ message: "Still saving", code: "send_rejected", isPaid: false, t })).toEqual({
      kind: "send_rejected",
      message: "chat.send_rejected",
    });
  });

  it("names the plan's limit by code, never by the English", () => {
    expect(
      resolveChatError({ message: "Reworded limit.", code: "quota_exceeded", isPaid: false, t }),
    ).toEqual({ kind: "quota", message: "chat.quota_exceeded_free" });
    expect(
      resolveChatError({ message: "Image limit.", code: "daily_limit", isPaid: true, t }).message,
    ).toBe("chat.quota_exceeded_pro");
    // The words alone are not a code: a spend-cap message is not an upgrade prompt.
    expect(
      resolveChatError({ message: "You've used up today's free limit.", isPaid: false, t }).kind,
    ).toBe("generic");
  });

  it("falls back for an empty message", () => {
    expect(resolveChatError({ message: "", isPaid: false, t })).toEqual({
      kind: "generic",
      message: "chat.error_generic",
    });
  });
});
