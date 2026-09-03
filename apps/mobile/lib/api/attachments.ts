import { request } from "@/lib/api/client";

function deleteAttachment(token: string, attachmentId: string) {
  return request<void>(`/attachments/${attachmentId}`, token, {
    method: "DELETE",
  });
}

export const attachmentsApi = {
  registerPushToken: (
    token: string,
    body: { expo_push_token: string; platform: string; device_id?: string },
  ) =>
    request<void>("/users/push-token", token, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  unregisterPushToken: (token: string, body: { expo_push_token: string }) =>
    request<void>("/users/push-token", token, {
      method: "DELETE",
      body: JSON.stringify(body),
    }),
  presignAttachment: (
    token: string,
    body: { content_type: string; size_bytes: number; filename?: string },
  ) =>
    request<{
      attachment_id: string;
      upload_url: string;
      storage_key: string;
      headers: Record<string, string>;
      api_upload: boolean;
    }>("/attachments/presign", token, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteAttachment,
  /** Composer cancel of an unlinked upload — same DELETE as Library delete. */
  cancelAttachment: deleteAttachment,
  confirmAttachment: (token: string, attachmentId: string) =>
    request<void>(`/attachments/${attachmentId}/confirm`, token, {
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
    }>(`/attachments/${attachmentId}/url`, token),
  listAttachments: (
    token: string,
    params: {
      category?: "images" | "files";
      source?: "upload" | "generated";
      q?: string;
      limit?: number;
      offset?: number;
    } = {},
  ) => {
    const search = new URLSearchParams();
    if (params.category) search.set("category", params.category);
    if (params.source) search.set("source", params.source);
    if (params.q) search.set("q", params.q);
    if (params.limit !== undefined) search.set("limit", String(params.limit));
    if (params.offset !== undefined) search.set("offset", String(params.offset));
    const qs = search.toString();
    return request<AttachmentListResponse>(
      qs ? `/attachments?${qs}` : "/attachments",
      token,
    );
  },
};

/** True if the Library row exists, false on 404, null if the probe itself failed. */
export async function attachmentRecordExists(
  token: string,
  attachmentId: string,
): Promise<boolean | null> {
  try {
    await request(`/attachments/${attachmentId}/url`, token);
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

export type AttachmentListItem = {
  id: string;
  content_type: string;
  size_bytes: number;
  download_url: string;
  source: "upload" | "generated";
  created_at: string;
  chat_id?: string | null;
  message_id?: string | null;
  original_filename?: string | null;
  chat_title?: string | null;
};

export type AttachmentListResponse = {
  items: AttachmentListItem[];
  has_more: boolean;
};
