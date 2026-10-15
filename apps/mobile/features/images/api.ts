import { request } from "@/lib/api/client";
import type { Message } from "@/lib/api/types";

export type ImageGenerateResult = {
  user_message: Message;
  assistant_message: Message;
};

/** The subject that owns a composer turn; `null` leaves it to image generation. */
export type ImageIntentResult = {
  subject: "math" | "physics" | "chemistry" | null;
};

/** A slow answer must not hold a picture request for long; see `stemSubjectOwnsTurn`. */
const IMAGE_INTENT_TIMEOUT_MS = 5_000;

export const imagesApi = {
  generateImage: (
    token: string,
    body: {
      chat_id: string;
      prompt: string;
      user_message?: string | null;
      aspect_ratio?: string | null;
      reference_attachment_ids?: string[];
    },
    init?: RequestInit,
  ) =>
    request<ImageGenerateResult>(
      "/images/generate",
      token,
      {
        method: "POST",
        body: JSON.stringify(body),
        ...init,
      },
      true,
      120_000,
    ),
  imageIntent: (token: string, text: string, init?: RequestInit) =>
    request<ImageIntentResult>(
      "/images/intent",
      token,
      {
        method: "POST",
        body: JSON.stringify({ text }),
        ...init,
      },
      true,
      IMAGE_INTENT_TIMEOUT_MS,
    ),
};
