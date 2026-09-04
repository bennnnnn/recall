import type React from "react";
import { act, renderHook } from "@testing-library/react-native";
import { useImageGeneration } from "@/hooks/useImageGeneration";
import { api, type Message } from "@/lib/api";
import { uploadChatAttachment, type PendingAttachment } from "@/lib/attachments";

jest.mock("@/lib/api", () => ({ api: { generateImage: jest.fn() } }));
jest.mock("@/lib/api/client", () => ({ ApiRequestError: class extends Error {} }));
jest.mock("@/lib/attachments", () => ({ uploadChatAttachment: jest.fn() }));
jest.mock("@/lib/haptics", () => ({ notifyWarning: jest.fn() }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/lib/cache/galleryListCache", () => ({ invalidateGalleryCache: jest.fn() }));

describe("image generation queued state and cancellation", () => {
  beforeEach(() => jest.clearAllMocks());

  async function setup() {
    const updates: React.SetStateAction<Message[]>[] = [];
    const count = { current: 0 };
    const rendered = await renderHook(() => useImageGeneration({
      token: "tok", chatId: "chat", setChatId: jest.fn(), setChatTitle: jest.fn(),
      setMessages: (update) => { updates.push(update); },
      draft: {} as never, router: {} as never, selectedModel: "free-chat", streaming: false,
      isPro: true, isOffline: false, onOpenUpgrade: jest.fn(), onScrollToLatest: jest.fn(),
      newMessageCountRef: count, t: (key) => key,
    }));
    const replay = () => updates.reduce<Message[]>((rows, update) => typeof update === "function" ? update(rows) : update, []);
    return { ...rendered, count, replay };
  }

  it("replaces the optimistic user even when React defers every message updater", async () => {
    const saved = { user_message: { id: "saved-user", role: "user", content: "Draw a cat" },
      assistant_message: { id: "saved-image", role: "assistant", content: "image" } };
    (api.generateImage as jest.Mock).mockResolvedValue(saved);
    const { result, count, replay } = await setup();
    await act(async () => { await result.current.submitPrompt({ prompt: "cat", userMessage: "Draw a cat" }); });
    expect(replay().map((row) => row.id)).toEqual(["saved-user", "saved-image"]);
    expect(count.current).toBe(2);
  });

  it("cancels during upload and retries with that same reference without another upload", async () => {
    let finishUpload!: (id: string) => void;
    (uploadChatAttachment as jest.Mock).mockImplementation(() => new Promise((resolve) => { finishUpload = resolve; }));
    (api.generateImage as jest.Mock).mockResolvedValue({
      user_message: { id: "saved-user", role: "user", content: "Make it blue" },
      assistant_message: { id: "saved-image", role: "assistant", content: "image" },
    });
    const { result, replay } = await setup();
    let pending!: Promise<void>;
    await act(async () => {
      pending = result.current.submitPrompt({ prompt: "Make it blue", userMessage: "Make it blue",
        referenceAttachment: { localUri: "file:///reference.png", kind: "image", contentType: "image/png", fileName: "reference.png" } satisfies PendingAttachment });
      await Promise.resolve();
    });
    await act(async () => { result.current.cancel(); finishUpload("original-reference"); await pending; });
    expect(api.generateImage).not.toHaveBeenCalled();
    expect(replay().at(-1)?.image_gen_failure).toBe("canceled");
    await act(async () => { result.current.retry(); await Promise.resolve(); await Promise.resolve(); });
    expect(uploadChatAttachment).toHaveBeenCalledTimes(1);
    expect(api.generateImage).toHaveBeenCalledWith("tok", expect.objectContaining({ reference_attachment_ids: ["original-reference"] }), expect.anything());
    expect(replay().map((row) => row.id)).toEqual(["saved-user", "saved-image"]);
  });
});
