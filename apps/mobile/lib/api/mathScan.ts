import { File } from "expo-file-system";

import { request } from "@/lib/api/client";
import { arrayBufferToBase64 } from "@/lib/base64";
import { getSessionGeneration, requireTokenSession, SessionChangedError } from "@/lib/auth";

export type MathScanExtractResult = {
  display_text: string;
  found: boolean;
  source: "mathpix" | "vision" | "none";
  confidence: number | null;
  uncertain: boolean;
};

export async function extractMathScan(
  token: string,
  pending: { localUri: string; contentType: string },
  signal?: AbortSignal,
): Promise<MathScanExtractResult> {
  requireTokenSession(token);
  const generation = getSessionGeneration();
  const file = new File(pending.localUri);
  if (!file.exists) throw new Error("Could not read the selected file.");
  const bytes = await file.arrayBuffer();
  if (generation !== getSessionGeneration()) throw new SessionChangedError();
  return request<MathScanExtractResult>(
    "/math/scan-extract",
    token,
    {
      method: "POST",
      body: JSON.stringify({
        image_base64: arrayBufferToBase64(bytes),
        content_type: pending.contentType,
      }),
      signal,
    },
    true,
    25_000,
  );
}

export const mathScanApi = {
  extractMathScan,
};
