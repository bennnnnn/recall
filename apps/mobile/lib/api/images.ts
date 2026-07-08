import { request } from "@/lib/api/client";
import type { Message } from "@/lib/api/types";

export type ImageGenerateResult = {
  user_message: Message;
  assistant_message: Message;
};

export const imagesApi = {
  generateImage: (
    token: string,
    body: { chat_id: string; prompt: string; aspect_ratio?: string | null },
  ) =>
    request<ImageGenerateResult>(
      "/images/generate",
      token,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
      true,
      120_000,
    ),
};
