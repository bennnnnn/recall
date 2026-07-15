import { request } from "@/lib/api/client";

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
    body: { content_type: string; size_bytes: number },
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
  cancelAttachment: (token: string, attachmentId: string) =>
    request<void>(`/attachments/${attachmentId}`, token, {
      method: "DELETE",
    }),
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
    }>(`/attachments/${attachmentId}/url`, token),
};
