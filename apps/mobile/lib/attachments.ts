import * as DocumentPicker from "expo-document-picker";
import * as ImagePicker from "expo-image-picker";
import * as ImageManipulator from "expo-image-manipulator";
import { File } from "expo-file-system";

import { api } from "@/lib/api";
import { uploadAttachmentBytes } from "@/lib/api/attachments";
import { getSessionGeneration, requireTokenSession, SessionChangedError } from "@/lib/auth";
import { MATH_CAMERA_PROMPT } from "@/lib/mathCameraPrompt";

export type AttachmentKind = "image" | "file";

export type PendingAttachment = {
  localUri: string;
  contentType: string;
  fileName: string;
  kind: AttachmentKind;
  /** Library item already on the server — skip re-upload; the API clones if linked. */
  existingAttachmentId?: string;
};

const DOCUMENT_MIME_TYPES = [
  "application/pdf",
  "text/plain",
  "text/markdown",
  "text/csv",
  "application/json",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
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
  const documentTypes: Record<string, string> = {
    pdf: "application/pdf", txt: "text/plain", md: "text/markdown",
    csv: "text/csv", json: "application/json",
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  };
  if (ext && documentTypes[ext]) return documentTypes[ext];
  if (ext === "heic") return "image/heic";
  if (ext === "heif") return "image/heif";
  if (ext === "png") return "image/png";
  if (ext === "webp") return "image/webp";
  if (ext === "gif") return "image/gif";
  if (ext === "jpg" || ext === "jpeg") return "image/jpeg";
  return "application/octet-stream";
}

export class HeicUnsupportedError extends Error {
  constructor() {
    super("HEIC_UNSUPPORTED");
    this.name = "HeicUnsupportedError";
  }
}

function isHeicContentType(contentType: string): boolean {
  return contentType === "image/heic" || contentType === "image/heif";
}

async function convertHeicToJpeg(uri: string): Promise<{ uri: string; fileName: string }> {
  const result = await ImageManipulator.manipulateAsync(
    uri,
    [],
    { compress: 0.9, format: ImageManipulator.SaveFormat.JPEG },
  );
  const baseName = uri.split("/").pop()?.split("?")[0] ?? "image";
  const stem = baseName.replace(/\.(heic|heif)$/i, "");
  return { uri: result.uri, fileName: `${stem}-${Date.now()}.jpg` };
}

async function assetToPending(
  uri: string,
  contentType: string,
  fileName: string,
): Promise<PendingAttachment> {
  const normalizedType = normalizeContentType(contentType, fileName || uri);
  if (isHeicContentType(normalizedType)) {
    // Auto-convert HEIC/HEIF to JPEG — most iPhone photos are HEIC by default,
    // and rejecting them created a poor UX. expo-image-manipulator is already
    // a dependency (used by the math scanner).
    const converted = await convertHeicToJpeg(uri);
    return {
      localUri: converted.uri,
      contentType: "image/jpeg",
      fileName: converted.fileName,
      kind: "image",
    };
  }
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

export { MATH_CAMERA_PROMPT };

export function defaultMathCameraPrompt(): string {
  return MATH_CAMERA_PROMPT;
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
    return await assetToPending(
      asset.uri,
      asset.mimeType ?? "",
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
    return await assetToPending(
      asset.uri,
      asset.mimeType ?? "",
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
    return await assetToPending(
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
  requireTokenSession(token);
  const generation = getSessionGeneration();
  const requireCurrent = () => {
    if (generation !== getSessionGeneration()) throw new SessionChangedError();
  };
  if (pending.existingAttachmentId) return pending.existingAttachmentId;

  const file = new File(pending.localUri);
  if (!file.exists) throw new Error("Could not read the selected file.");
  const sizeBytes = file.size;
  if (!Number.isSafeInteger(sizeBytes) || sizeBytes <= 0) {
    throw new Error("Could not determine file size.");
  }
  const presign = await api.presignAttachment(token, {
    content_type: pending.contentType,
    size_bytes: sizeBytes,
    filename: pending.fileName,
  });
  try {
    requireCurrent();
    const bytes = await file.arrayBuffer();
    requireCurrent();
    if (bytes.byteLength !== sizeBytes) throw new Error("The selected file changed. Please attach it again.");
    await uploadAttachmentBytes(token, presign, pending.contentType, bytes);
    requireCurrent();

    if (!presign.api_upload) {
      await api.confirmAttachment(token, presign.attachment_id);
      requireCurrent();
    }

    try {
      const { invalidateGalleryCache } = await import("@/lib/cache/galleryListCache");
      invalidateGalleryCache();
    } catch {
      /* best-effort */
    }

    requireCurrent();
    return presign.attachment_id;
  } catch (error) {
    try {
      await api.cancelAttachment(token, presign.attachment_id);
    } catch {
      /* best-effort refund */
    }
    throw error;
  }
}
