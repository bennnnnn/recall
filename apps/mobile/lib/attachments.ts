import * as DocumentPicker from "expo-document-picker";
import * as ImagePicker from "expo-image-picker";
import { getInfoAsync } from "expo-file-system/legacy";

import { api } from "@/lib/api";
import { getApiUrl } from "@/lib/config";

export type AttachmentKind = "image" | "file";

export type PendingAttachment = {
  localUri: string;
  contentType: string;
  fileName: string;
  kind: AttachmentKind;
};

const DOCUMENT_MIME_TYPES = [
  "application/pdf",
  "text/plain",
  "text/markdown",
  "text/csv",
  "application/json",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];

let nativePickerActive = false;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isPickerConflictError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return message.toLowerCase().includes("document picking in progress");
}

async function withNativePicker<T>(run: () => Promise<T>): Promise<T | null> {
  if (nativePickerActive) return null;
  nativePickerActive = true;
  try {
    let lastError: unknown;
    for (let attempt = 0; attempt < 4; attempt += 1) {
      try {
        return await run();
      } catch (error) {
        lastError = error;
        if (!isPickerConflictError(error) || attempt === 3) throw error;
        await sleep(300 * (attempt + 1));
      }
    }
    throw lastError;
  } finally {
    nativePickerActive = false;
  }
}

function guessKind(contentType: string): AttachmentKind {
  return contentType.startsWith("image/") ? "image" : "file";
}

function normalizeContentType(mimeType: string | null | undefined, uri: string): string {
  const base = (mimeType ?? "").split(";")[0].trim().toLowerCase();
  if (base && base !== "application/octet-stream") {
    if (base === "image/jpg" || base === "image/pjpeg") return "image/jpeg";
    return base;
  }
  const ext = uri.split("?")[0]?.split(".").pop()?.toLowerCase();
  if (ext === "heic") return "image/heic";
  if (ext === "heif") return "image/heif";
  if (ext === "png") return "image/png";
  if (ext === "webp") return "image/webp";
  if (ext === "gif") return "image/gif";
  return "image/jpeg";
}

function assetToPending(
  uri: string,
  contentType: string,
  fileName: string,
): PendingAttachment {
  const normalizedType = normalizeContentType(contentType, uri);
  return {
    localUri: uri,
    contentType: normalizedType,
    fileName,
    kind: guessKind(normalizedType),
  };
}

export function attachmentPreviewLabel(pending: PendingAttachment): string {
  const icon = pending.kind === "image" ? "📷" : "📎";
  return `${icon} ${pending.fileName}`;
}

export function defaultAttachmentPrompt(pending: PendingAttachment): string {
  return pending.kind === "image" ? "" : "Summarize this file.";
}

/** Text sent to the API for a message that may include an attachment. */
export function messageTextForSend(
  text: string,
  attached: PendingAttachment | null | undefined,
): string {
  const trimmed = text.trim();
  if (trimmed) return trimmed;
  if (!attached) return "";
  return defaultAttachmentPrompt(attached);
}

export async function pickFromPhotoLibrary(): Promise<PendingAttachment | null> {
  return withNativePicker(async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      throw new Error("Photo library permission is required to attach photos.");
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      quality: 0.85,
      allowsEditing: false,
    });

    if (result.canceled || !result.assets[0]) return null;

    const asset = result.assets[0];
    return assetToPending(
      asset.uri,
      asset.mimeType ?? "image/jpeg",
      asset.fileName ?? `photo-${Date.now()}.jpg`,
    );
  });
}

export async function pickFromCamera(): Promise<PendingAttachment | null> {
  return withNativePicker(async () => {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) {
      throw new Error("Camera permission is required to take photos.");
    }

    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ["images"],
      quality: 0.85,
      allowsEditing: false,
    });

    if (result.canceled || !result.assets[0]) return null;

    const asset = result.assets[0];
    return assetToPending(
      asset.uri,
      asset.mimeType ?? "image/jpeg",
      asset.fileName ?? `camera-${Date.now()}.jpg`,
    );
  });
}

export async function pickDocument(): Promise<PendingAttachment | null> {
  return withNativePicker(async () => {
    await sleep(150);
    const result = await DocumentPicker.getDocumentAsync({
      type: ["image/*", ...DOCUMENT_MIME_TYPES],
      copyToCacheDirectory: true,
      multiple: false,
    });

    if (result.canceled || !result.assets[0]) return null;

    const asset = result.assets[0];
    const contentType = asset.mimeType ?? "application/octet-stream";
    return assetToPending(
      asset.uri,
      contentType,
      asset.name ?? `file-${Date.now()}`,
    );
  });
}

export async function uploadChatAttachment(
  token: string,
  pending: PendingAttachment,
): Promise<string> {
  const info = await getInfoAsync(pending.localUri);
  if (!info.exists) throw new Error("Could not read the selected file.");

  const sizeBytes = "size" in info && typeof info.size === "number" ? info.size : 0;
  if (!sizeBytes || sizeBytes <= 0) {
    throw new Error("Could not determine file size.");
  }

  const presign = await api.presignAttachment(token, {
    content_type: pending.contentType,
    size_bytes: sizeBytes,
  });

  const fileResponse = await fetch(pending.localUri);
  if (!fileResponse.ok) {
    throw new Error("Could not read the selected file.");
  }
  const bytes = await fileResponse.arrayBuffer();

  const uploadPath = presign.api_upload
    ? `/attachments/${presign.attachment_id}/upload`
    : presign.upload_url;

  const uploadUrl = uploadPath.startsWith("http")
    ? uploadPath
    : `${getApiUrl()}${uploadPath.startsWith("/") ? uploadPath : `/${uploadPath}`}`;

  const headers: Record<string, string> = {
    "Content-Type": pending.contentType,
  };
  if (presign.api_upload || uploadUrl.startsWith(getApiUrl())) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(uploadUrl, {
    method: "PUT",
    headers,
    body: bytes,
  });

  if (!response.ok) {
    throw new Error("Upload failed.");
  }

  if (!presign.api_upload) {
    await api.confirmAttachment(token, presign.attachment_id);
  }

  return presign.attachment_id;
}
