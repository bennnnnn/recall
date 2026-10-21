type ChatErrorKind = "quota" | "model_unavailable" | "busy" | "send_rejected" | "attachment_rejected" | "generic";

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
  // An image's daily limit is the plan's limit too.
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
