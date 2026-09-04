import { request } from "@/lib/api/client";
import type { Message } from "@/lib/api/types";

export type ImageGenerateResult = {
  user_message: Message;
  assistant_message: Message;
};

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
};
