import { ApiRequestError } from "@/lib/api/client";
import { MAX_ATTACHMENT_MEGABYTES } from "@/features/attachments/model/attachmentLimits";

/** Why an attachment could not be picked or uploaded. Each reason has one message. */
export type AttachmentFailure =
  | "too_large"
  | "unsupported_type"
  | "unreadable"
  | "changed"
  | "upload_failed"
  | "daily_limit"
  | "camera_permission";

export class AttachmentError extends Error {
  readonly reason: AttachmentFailure;
  constructor(reason: AttachmentFailure) {
    super(`ATTACHMENT_${reason.toUpperCase()}`);
    this.name = "AttachmentError";
    this.reason = reason;
  }
}

const MESSAGE_KEYS: Record<AttachmentFailure, string> = {
  too_large: "chat.attach_too_large",
  unsupported_type: "chat.attach_unsupported_type",
  unreadable: "chat.attach_unreadable",
  changed: "chat.attach_changed",
  upload_failed: "chat.attach_upload_failed",
  daily_limit: "chat.attach_daily_limit",
  camera_permission: "chat.camera_permission",
};

type Translate = (key: string, options?: Record<string, unknown>) => string;

/** The toast for a failed pick or upload. Anything untyped is the generic message, never raw text. */
export function attachmentErrorMessage(error: unknown, t: Translate): string {
  if (!(error instanceof AttachmentError)) return t("chat.attach_failed");
  return t(MESSAGE_KEYS[error.reason], { limit: MAX_ATTACHMENT_MEGABYTES });
}

function apiDetail(error: ApiRequestError): string {
  try {
    const body = JSON.parse(error.message) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? "");
  } catch {
    return error.message;
  }
}

/**
 * Presign refusals named by the API (modules/attachments/upload.py): 400 for an
 * unsupported type or a bad size, 422 when `size_bytes` breaks the schema cap,
 * 429 for the daily image limit. Any other API refusal is a failed upload; a
 * non-API error (session change, network) passes through unchanged.
 */
export function presignFailure(error: unknown): unknown {
  if (!(error instanceof ApiRequestError)) return error;
  const detail = apiDetail(error);
  if (error.status === 429) return new AttachmentError("daily_limit");
  if (error.status === 400 && /content type/i.test(detail)) return new AttachmentError("unsupported_type");
  if ((error.status === 400 || error.status === 422) && /size/i.test(detail)) {
    return new AttachmentError("too_large");
  }
  return new AttachmentError("upload_failed");
}
