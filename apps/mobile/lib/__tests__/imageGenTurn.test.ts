import { IMAGE_GEN_FAILED_ASSISTANT_ID, IMAGE_GEN_PENDING_ASSISTANT_ID } from "@/lib/imageGenIntent";
import {
  applyImageGenFailure,
  hasImageGenFailedAssistant,
  imageGenUserBubble,
  restoreImageGenPending,
} from "@/lib/imageGenTurn";
import type { Message } from "@/lib/api";

function row(id: string, role: Message["role"], content: string): Message {
  return {
    id,
    role,
    content,
    model: null,
    created_at: "2026-01-01T00:00:00.000Z",
  };
}

describe("imageGenUserBubble", () => {
  it("keeps the words the user typed", () => {
    expect(imageGenUserBubble("create a cat image", "cat")).toBe("create a cat image");
  });

  it("does not rewrite to Generate image: prefix", () => {
    expect(imageGenUserBubble("create a cat image", "cat")).not.toMatch(/^Generate image:/i);
  });
});

describe("image gen failure card", () => {
  const pending = [
    row("local-img-1", "user", "create a cat image"),
    row(IMAGE_GEN_PENDING_ASSISTANT_ID, "assistant", ""),
  ];

  it("keeps the user bubble and marks the assistant canceled", () => {
    const next = applyImageGenFailure(pending, "canceled");
    expect(next[0]?.content).toBe("create a cat image");
    expect(next[1]?.id).toBe(IMAGE_GEN_FAILED_ASSISTANT_ID);
    expect(next[1]?.image_gen_failure).toBe("canceled");
    expect(hasImageGenFailedAssistant(next)).toBe(true);
  });

  it("restores the pending card for retry", () => {
    const failed = applyImageGenFailure(pending, "failed", "Couldn't create the image");
    const next = restoreImageGenPending(failed);
    expect(next[0]?.content).toBe("create a cat image");
    expect(next[1]?.id).toBe(IMAGE_GEN_PENDING_ASSISTANT_ID);
    expect(next[1]?.image_gen_failure).toBeUndefined();
  });
});
