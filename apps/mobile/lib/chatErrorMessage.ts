import { isQuotaErrorMessage } from "@/lib/quota";

export type ChatErrorKind = "quota" | "model_unavailable" | "busy" | "generic";

export type ResolvedChatError = {
  kind: ChatErrorKind;
  message: string;
};

export function parseApiErrorDetail(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return null;
  try {
    const parsed = JSON.parse(trimmed) as { detail?: unknown };
    const detail = parsed.detail;
    if (typeof detail === "string" && detail.trim()) return detail.trim();
    if (Array.isArray(detail)) {
      const parts = detail
        .map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg?: string }).msg ?? "");
          }
          return "";
        })
        .filter(Boolean);
      if (parts.length) return parts.join(", ");
    }
  } catch {
    return null;
  }
  return null;
}

export function resolveChatError(options: {
  message: string;
  code?: string;
  isPro: boolean;
  t: (key: string) => string;
}): ResolvedChatError {
  const parsed = parseApiErrorDetail(options.message);
  const text = (parsed ?? options.message).trim();

  if (options.code === "busy") {
    return { kind: "busy", message: options.t("chat.busy") };
  }
  if (options.code === "model_unavailable") {
    return { kind: "model_unavailable", message: options.t("chat.model_unavailable") };
  }
  if (options.code === "quota_exceeded" || isQuotaErrorMessage(text)) {
    return {
      kind: "quota",
      message:
        text ||
        options.t(options.isPro ? "chat.quota_exceeded_pro" : "chat.quota_exceeded_free"),
    };
  }
  if (!text || text.startsWith("{") || text.startsWith("[")) {
    return { kind: "generic", message: options.t("chat.error_generic") };
  }
  return { kind: "generic", message: text };
}
