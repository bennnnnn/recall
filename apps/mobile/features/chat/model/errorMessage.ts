import { UNAVAILABLE_CODE } from "@/lib/api/errorBody";

type ChatErrorKind =
  | "quota"
  | "model_unavailable"
  | "busy"
  | "send_rejected"
  | "attachment_rejected"
  /** Said and dismissed: nothing to retry or buy (a refused picture, a paid plan's cap). */
  | "notice"
  | "generic";

/**
 * The code a refusal is worded by. A `daily_limit` names its feature: a picture's own
 * cap is not the day's chat allowance running out.
 */
export function refusalCode(code: string | undefined, feature: unknown): string | undefined {
  return code === "daily_limit" && feature === "image_generation" ? "image_daily_limit" : code;
}

export type ResolvedChatError = {
  kind: ChatErrorKind;
  message: string;
};

export function resolveChatError(options: {
  message: string;
  code?: string;
  isPaid: boolean;
  t: (key: string) => string;
}): ResolvedChatError {
  const text = options.message.trim();

  if (options.code === "attachment_rejected") {
    return { kind: "attachment_rejected", message: options.t("chat.attachment_rejected") };
  }
  if (options.code === "send_rejected") {
    return { kind: "send_rejected", message: options.t("chat.send_rejected") };
  }
  if (options.code === "busy") {
    return { kind: "busy", message: options.t("chat.busy") };
  }
  if (options.code === "model_unavailable") {
    return { kind: "model_unavailable", message: options.t("chat.model_unavailable") };
  }
  // Recall's database or Redis is down (the socket's frame, a 503's body): its own words,
  // translated, where the server's English showed.
  if (options.code === UNAVAILABLE_CODE) {
    return { kind: "generic", message: options.t("common.service_unavailable") };
  }
  if (options.code === "image_daily_limit") {
    // A free plan can buy more pictures; a paid one waits for tomorrow.
    return options.isPaid
      ? { kind: "notice", message: options.t("chat.image_daily_limit_paid") }
      : { kind: "quota", message: options.t("chat.image_daily_limit_free") };
  }
  if (options.code === "content_blocked") {
    return { kind: "notice", message: options.t("chat.image_content_blocked") };
  }
  if (options.code === "quota_exceeded" || options.code === "daily_limit") {
    return {
      kind: "quota",
      message: options.t(options.isPaid ? "chat.quota_exceeded_pro" : "chat.quota_exceeded_free"),
    };
  }
  if (!text || text.startsWith("{") || text.startsWith("[")) {
    return { kind: "generic", message: options.t("chat.error_generic") };
  }
  return { kind: "generic", message: text };
}
