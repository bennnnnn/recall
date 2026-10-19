import { File } from "expo-file-system";
import { ImageManipulator, type ImageManipulatorContext, type ImageRef, SaveFormat } from "expo-image-manipulator";

import { AttachmentError } from "@/features/attachments/model/attachmentErrors";
import {
  DOCUMENT_MIME_TYPES,
  IMAGE_JPEG_QUALITY,
  MAX_ATTACHMENT_BYTES,
  MAX_IMAGE_EDGE,
  UPLOADABLE_IMAGE_TYPES,
} from "@/features/attachments/model/attachmentLimits";
import { adoptLocalCopy, discardLocalCopy } from "@/features/attachments/model/localAttachmentFile";

/** What a picker returned, with its content type already normalized. */
export type PickedAsset = {
  uri: string;
  contentType: string;
  fileName: string;
  /** Pixel size when the picker reports it; Files picks do not. */
  width?: number;
  height?: number;
};

export type PreparedAttachment = {
  localUri: string;
  contentType: string;
  fileName: string;
  kind: "image" | "file";
};

/** Size of a local file; a missing or empty file cannot be sent. */
export function localFileSize(uri: string): number {
  const file = new File(uri);
  if (!file.exists) throw new AttachmentError("unreadable");
  const size = file.size;
  if (!Number.isSafeInteger(size) || size <= 0) throw new AttachmentError("unreadable");
  return size;
}

function fitsAsSent(contentType: string, width: number, height: number, uri: string): boolean {
  return (
    UPLOADABLE_IMAGE_TYPES.has(contentType) &&
    width > 0 && height > 0 &&
    Math.max(width, height) <= MAX_IMAGE_EDGE &&
    localFileSize(uri) <= MAX_ATTACHMENT_BYTES
  );
}

function jpegFileName(fileName: string): string {
  const stem = fileName.replace(/\.[^./]+$/, "") || "photo";
  return `${stem}.jpg`;
}

/**
 * Every picked photo leaves here as something the API accepts: an allowed type
 * no larger than MAX_IMAGE_EDGE on its long edge, sent untouched (a GIF keeps
 * its animation), or else re-encoded as a JPEG (HEIC, TIFF, a full-size camera frame).
 */
async function prepareImage(asset: PickedAsset): Promise<PreparedAttachment> {
  const asSent: PreparedAttachment = {
    localUri: asset.uri, contentType: asset.contentType, fileName: asset.fileName, kind: "image",
  };
  if (asset.width && asset.height && fitsAsSent(asset.contentType, asset.width, asset.height, asset.uri)) {
    return asSent;
  }
  const contexts: ImageManipulatorContext[] = [ImageManipulator.manipulate(asset.uri)];
  const images: ImageRef[] = [];
  try {
    let image = await contexts[0].renderAsync();
    images.push(image);
    if (fitsAsSent(asset.contentType, image.width, image.height, asset.uri)) return asSent;
    if (Math.max(image.width, image.height) > MAX_IMAGE_EDGE) {
      const resize = ImageManipulator.manipulate(image).resize(
        image.width >= image.height ? { width: MAX_IMAGE_EDGE } : { height: MAX_IMAGE_EDGE },
      );
      contexts.push(resize);
      image = await resize.renderAsync();
      images.push(image);
    }
    const saved = await image.saveAsync({ format: SaveFormat.JPEG, compress: IMAGE_JPEG_QUALITY });
    adoptLocalCopy(saved.uri);
    return { localUri: saved.uri, contentType: "image/jpeg", fileName: jpegFileName(asset.fileName), kind: "image" };
  } catch (error) {
    if (error instanceof AttachmentError) throw error;
    // An allowed type that will not decode is damaged; anything else (SVG, RAW) is a type we cannot take.
    throw new AttachmentError(UPLOADABLE_IMAGE_TYPES.has(asset.contentType) ? "unreadable" : "unsupported_type");
  } finally {
    for (const image of images) image.release();
    for (const context of contexts) context.release();
  }
}

function prepareDocument(asset: PickedAsset): PreparedAttachment {
  if (!DOCUMENT_MIME_TYPES.includes(asset.contentType)) throw new AttachmentError("unsupported_type");
  return { localUri: asset.uri, contentType: asset.contentType, fileName: asset.fileName, kind: "file" };
}

/**
 * Turns a pick into a composer attachment the API will take, or refuses it
 * now with the reason, before Send. The picker's copy is removed when a
 * re-encode replaces it, and every copy made here is removed on a refusal.
 */
export async function preparePickedAsset(asset: PickedAsset): Promise<PreparedAttachment> {
  adoptLocalCopy(asset.uri);
  let prepared: PreparedAttachment | null = null;
  try {
    prepared = asset.contentType.startsWith("image/") ? await prepareImage(asset) : prepareDocument(asset);
    if (localFileSize(prepared.localUri) > MAX_ATTACHMENT_BYTES) throw new AttachmentError("too_large");
    if (prepared.localUri !== asset.uri) discardLocalCopy(asset.uri);
    return prepared;
  } catch (error) {
    discardLocalCopy(asset.uri);
    discardLocalCopy(prepared?.localUri);
    throw error;
  }
}
