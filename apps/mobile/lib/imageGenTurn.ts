import type { Message } from "@/lib/api";
import {
  IMAGE_GEN_FAILED_ASSISTANT_ID,
  IMAGE_GEN_PENDING_ASSISTANT_ID,
} from "@/lib/imageGenIntent";

export type ImageGenFailure = "canceled" | "failed";

/** Show what the user typed — never rewrite to "Generate image: …". */
export function imageGenUserBubble(userMessage: string, prompt: string): string {
  return userMessage.trim() || prompt.trim();
}

export function applyImageGenFailure(
  messages: readonly Message[],
  outcome: ImageGenFailure,
  errorText?: string,
): Message[] {
  return messages.map((row) =>
    row.id === IMAGE_GEN_PENDING_ASSISTANT_ID
      ? {
          ...row,
          id: IMAGE_GEN_FAILED_ASSISTANT_ID,
          content: "",
          image_gen_failure: outcome,
          image_gen_error: errorText,
        }
      : row,
  );
}

export function restoreImageGenPending(messages: readonly Message[]): Message[] {
  return messages.map((row) =>
    row.id === IMAGE_GEN_FAILED_ASSISTANT_ID
      ? {
          ...row,
          id: IMAGE_GEN_PENDING_ASSISTANT_ID,
          content: "",
          image_gen_failure: undefined,
          image_gen_error: undefined,
        }
      : row,
  );
}

export function hasImageGenFailedAssistant(messages: readonly Message[]): boolean {
  return messages.some((row) => row.id === IMAGE_GEN_FAILED_ASSISTANT_ID);
}
