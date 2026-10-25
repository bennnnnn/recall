import { refusalCode, resolveChatError } from "@/features/chat/model/errorMessage";

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

  it("says a picture's own limit, with an upgrade only where the plan can buy more", () => {
    expect(refusalCode("daily_limit", "image_generation")).toBe("image_daily_limit");
    expect(refusalCode("daily_limit", "speech_transcription")).toBe("daily_limit");
    expect(refusalCode("busy", undefined)).toBe("busy");
    expect(resolveChatError({ message: "x", code: "image_daily_limit", isPaid: false, t })).toEqual({
      kind: "quota",
      message: "chat.image_daily_limit_free",
    });
    expect(resolveChatError({ message: "x", code: "image_daily_limit", isPaid: true, t })).toEqual({
      kind: "notice",
      message: "chat.image_daily_limit_paid",
    });
  });

  it("says a refused picture is the content rules, with nothing to retry", () => {
    expect(resolveChatError({ message: "Blocked.", code: "content_blocked", isPaid: false, t })).toEqual({
      kind: "notice",
      message: "chat.image_content_blocked",
    });
  });

  // The socket's frames for a turn the spend gate refused. Redis down at the spend read sent
  // spend_cap too: "Recall is at capacity for today… Try again after midnight UTC."
  it("says the day's spend cap in the server's words, and an outage as Recall unavailable", () => {
    const capacity = "Recall is at capacity for today, so new messages are paused for everyone.";
    expect(resolveChatError({ message: capacity, code: "spend_cap", isPaid: false, t })).toEqual({
      kind: "generic",
      message: capacity,
    });
    expect(
      resolveChatError({ message: "Service temporarily unavailable.", code: "unavailable", isPaid: true, t }),
    ).toEqual({ kind: "generic", message: "common.service_unavailable" });
  });

  it("falls back for an empty message", () => {
    expect(resolveChatError({ message: "", isPaid: false, t })).toEqual({
      kind: "generic",
      message: "chat.error_generic",
    });
  });
});
