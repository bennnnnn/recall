import { request, requestRaw } from "@/lib/api/client";
import { apiPath, withQuery } from "@/lib/api/path";
import type { AttachmentListResponse } from "@/features/attachments/types";
import { getSessionGeneration, requireTokenSession, SessionChangedError } from "@/lib/auth";
import { AttachmentError } from "@/features/attachments/model/attachmentErrors";

async function deleteAttachment(token: string, attachmentId: string): Promise<void> {
  const generation = getSessionGeneration();
  await request<void>(apiPath`/attachments/${attachmentId}`, token, {
    method: "DELETE",
  });
  try {
    const { removeCachedAttachmentFiles } = await import("@/features/attachments/model/downloadChatAttachment");
    if (generation === getSessionGeneration()) await removeCachedAttachmentFiles(attachmentId);
  } catch {
    // Remote deletion already succeeded; a device cache failure must not undo it.
  }
}

/**
 * What an upload is for. A chat file goes out with a message, so on a plan whose uploads
 * follow messages the server wants one left; a profile photo or a picture's reference
 * photo does not (apps/api modules/attachments/upload.py). A paste is a chat file holding
 * text pasted into the composer: the one upload the server reads as the user's own words,
 * so only the composer's paste sends it (attachments.ts uploadChatAttachment).
 */
export type UploadPurpose = "chat" | "paste" | "avatar" | "reference";

export const attachmentsApi = {
  presignAttachment: (
    token: string,
    body: { content_type: string; size_bytes: number; filename?: string; purpose?: UploadPurpose },
  ) =>
    request<{
      attachment_id: string;
      upload_url: string;
      headers: Record<string, string>;
      api_upload: boolean;
    }>("/attachments/presign", token, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteAttachment,
  /** What the account keeps in Library and its plan's total (Settings → Storage). */
  getLibraryStorage: (token: string) =>
    request<{ used_bytes: number; limit_bytes: number }>("/attachments/storage", token),
  /** Composer cancel of an unlinked upload — same DELETE as Library delete. */
  cancelAttachment: deleteAttachment,
  confirmAttachment: (token: string, attachmentId: string) =>
    request<void>(apiPath`/attachments/${attachmentId}/confirm`, token, {
      method: "POST",
    }),
  getAttachmentUrl: (token: string, attachmentId: string) =>
    request<{
      id: string;
      content_type: string;
      size_bytes: number;
      download_url: string;
      created_at: string;
      indexed?: boolean;
      original_filename?: string | null;
    }>(apiPath`/attachments/${attachmentId}/url`, token),
  listAttachments: (
    token: string,
    params: {
      category?: "images" | "files";
      source?: "upload" | "generated";
      q?: string;
      limit?: number;
      /** The `next_cursor` of the page before; omitted for the first page. */
      cursor?: string;
    } = {},
  ) => {
    const query = withQuery("/attachments", {
      category: params.category || undefined,
      source: params.source || undefined,
      q: params.q || undefined,
      limit: params.limit,
      cursor: params.cursor || undefined,
    });
    return request<AttachmentListResponse>(query, token);
  },
};

/** True if the Library row exists, false on 404, null if the probe itself failed. */
export async function attachmentRecordExists(
  token: string,
  attachmentId: string,
): Promise<boolean | null> {
  try {
    await request(apiPath`/attachments/${attachmentId}/url`, token);
    return true;
  } catch (error) {
    if (
      typeof error === "object" &&
      error !== null &&
      "status" in error &&
      error.status === 404
    ) {
      return false;
    }
    return null;
  }
}

const ATTACHMENT_UPLOAD_TIMEOUT_MS = 120_000;

/** API uploads share refresh/retry; presigned storage requests never receive Recall credentials. */
export async function uploadAttachmentBytes(
  token: string,
  target: { attachment_id: string; upload_url: string; api_upload: boolean; headers?: Record<string, string> },
  contentType: string,
  bytes: ArrayBuffer,
): Promise<void> {
  requireTokenSession(token);
  const generation = getSessionGeneration();
  const headers = { "Content-Type": contentType, ...target.headers };
  let response: Response;
  if (target.api_upload) {
    response = await requestRaw(apiPath`/attachments/${target.attachment_id}/upload`, token, {
      method: "PUT", headers, body: bytes,
    }, true, ATTACHMENT_UPLOAD_TIMEOUT_MS);
  } else {
    const url = new URL(target.upload_url);
    if (url.protocol !== "https:" || url.username || url.password) {
      throw new AttachmentError("upload_failed");
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), ATTACHMENT_UPLOAD_TIMEOUT_MS);
    try {
      response = await fetch(url.toString(), { method: "PUT", headers, body: bytes, signal: controller.signal });
    } finally {
      clearTimeout(timer);
    }
  }
  if (generation !== getSessionGeneration()) throw new SessionChangedError();
  if (!response.ok) throw new AttachmentError("upload_failed");
}
