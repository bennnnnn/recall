import type React from "react";
import { act, renderHook } from "@testing-library/react-native";
import { useImageGeneration } from "@/features/images/hooks/useImageGeneration";
import { api, type Message } from "@/lib/api";
import { uploadChatAttachment, type PendingAttachment } from "@/features/attachments/model/attachments";
import { ApiRequestError } from "@/lib/api/client";
import { notifyWarning } from "@/lib/haptics";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { invalidateGalleryCache } from "@/features/attachments/model/galleryListCache";

jest.mock("@/lib/api", () => ({ api: { generateImage: jest.fn() } }));
jest.mock("@/lib/api/client", () => ({
  ApiRequestError: class extends Error {
    status: number;
    constructor(code: number, message = "") {
      super(message);
      this.status = code;
    }
  },
}));
jest.mock("@/features/attachments/model/attachments", () => ({ uploadChatAttachment: jest.fn() }));
jest.mock("@/lib/haptics", () => ({ notifyWarning: jest.fn() }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/features/attachments/model/galleryListCache", () => ({ invalidateGalleryCache: jest.fn() }));
jest.mock("@/lib/reportRecoverableError", () => ({ reportRecoverableError: jest.fn() }));

describe("image generation queued state and cancellation", () => {
  beforeEach(() => jest.clearAllMocks());

  async function setup() {
    const updates: React.SetStateAction<Message[]>[] = [];
    const count = { current: 0 };
    const rendered = await renderHook(() => useImageGeneration({
      token: "tok", chatId: "chat", setChatId: jest.fn(), setChatTitle: jest.fn(),
      setMessages: (update) => { updates.push(update); },
      draft: {} as never, router: {} as never, selectedModel: "free-chat", streaming: false,
      isPaid: true, isOffline: false, onOpenUpgrade: jest.fn(), onScrollToLatest: jest.fn(),
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

  it("shows the optimistic turn while persistence gates provider generation", async () => {
    let finishPersistence!: (saved: boolean) => void;
    const persistenceReady = new Promise<boolean>((resolve) => {
      finishPersistence = resolve;
    });
    (api.generateImage as jest.Mock).mockResolvedValue({
      user_message: { id: "saved-user", role: "user", content: "Draw a cat" },
      assistant_message: { id: "saved-image", role: "assistant", content: "image" },
    });
    const { result, replay } = await setup();

    let pending!: Promise<void>;
    await act(async () => {
      pending = result.current.submitPrompt({
        prompt: "cat",
        userMessage: "Draw a cat",
        persistenceReady,
      });
      await Promise.resolve();
    });

    expect(replay().map((row) => row.id)).toEqual([
      expect.stringMatching(/^local-img-/),
      "image-gen-pending",
    ]);
    expect(api.generateImage).not.toHaveBeenCalled();

    await act(async () => {
      finishPersistence(true);
      await pending;
    });
    expect(api.generateImage).toHaveBeenCalledTimes(1);
  });

  it("aborts generation and restores the composer when persistence fails", async () => {
    const onPersistenceFailure = jest.fn();
    const { result, replay, count } = await setup();

    await act(async () => {
      await result.current.submitPrompt({
        prompt: "cat",
        userMessage: "Draw a cat",
        persistenceReady: Promise.resolve(false),
        onPersistenceFailure,
      });
    });

    expect(api.generateImage).not.toHaveBeenCalled();
    expect(replay()).toEqual([]);
    expect(count.current).toBe(0);
    expect(onPersistenceFailure).toHaveBeenCalledTimes(1);
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

describe("image generation submit steps", () => {
  const saved = {
    user_message: { id: "saved-user", role: "user", content: "Draw a cat" },
    assistant_message: { id: "saved-image", role: "assistant", content: "image" },
  };
  beforeEach(() => {
    jest.clearAllMocks();
    (api.generateImage as jest.Mock).mockResolvedValue(saved);
  });

  async function setup(overrides: Partial<Parameters<typeof useImageGeneration>[0]> = {}) {
    const updates: React.SetStateAction<Message[]>[] = [];
    const options = {
      token: "tok" as string | null, chatId: "chat" as string | null, setChatId: jest.fn(), setChatTitle: jest.fn(),
      setMessages: (update: React.SetStateAction<Message[]>) => { updates.push(update); },
      draft: {} as never, router: { setParams: jest.fn() } as never, selectedModel: "free-chat", streaming: false,
      isPaid: true, isOffline: false, onOpenUpgrade: jest.fn(), onOfflineBlocked: jest.fn(), onScrollToLatest: jest.fn(),
      newMessageCountRef: { current: 0 }, t: (key: string) => key,
      ...overrides,
    };
    const rendered = await renderHook(() => useImageGeneration(options));
    const replay = () => updates.reduce<Message[]>((rows, update) => typeof update === "function" ? update(rows) : update, []);
    const submit = async (input: Parameters<ReturnType<typeof useImageGeneration>["submitPrompt"]>[0]) => {
      await act(async () => { await rendered.result.current.submitPrompt(input); });
    };
    return { ...rendered, options, updates, replay, submit };
  }

  it.each([
    ["no session", { token: null }],
    ["an empty prompt", {}],
  ])("does nothing with %s", async (label, overrides) => {
    const { submit, updates } = await setup(overrides);
    await submit({ prompt: label === "an empty prompt" ? "  " : "cat", userMessage: "" });
    expect(updates).toEqual([]);
    expect(api.generateImage).not.toHaveBeenCalled();
  });

  it("asks the user to wait while a chat reply streams", async () => {
    const { submit, updates } = await setup({ streaming: true });
    await submit({ prompt: "cat", userMessage: "Draw a cat" });
    expect(reportRecoverableError).toHaveBeenCalledWith(null, "chat.busy");
    expect(updates).toEqual([]);
  });

  it("keeps the request offline and says so", async () => {
    const { submit, updates, options } = await setup({ isOffline: true });
    await submit({ prompt: "cat", userMessage: "Draw a cat" });
    expect(notifyWarning).toHaveBeenCalledTimes(1);
    expect(options.onOfflineBlocked).toHaveBeenCalledTimes(1);
    expect(updates).toEqual([]);
  });

  it("ignores a second request while one is generating", async () => {
    let finish!: (value: typeof saved) => void;
    (api.generateImage as jest.Mock).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
    const { result } = await setup();
    let first!: Promise<void>;
    await act(async () => { first = result.current.submitPrompt({ prompt: "cat", userMessage: "Draw a cat" }); });
    await act(async () => { await result.current.submitPrompt({ prompt: "dog", userMessage: "Draw a dog" }); });
    expect(api.generateImage).toHaveBeenCalledTimes(1);
    expect(result.current.generating).toBe(true);
    await act(async () => { finish(saved); await first; });
    expect(result.current.generating).toBe(false);
  });

  it("creates a new chat first when none is open", async () => {
    const draft = {
      creatingRef: { current: false }, skipLoadForChatIdRef: { current: null as string | null },
      draftChatIdRef: { current: "new-1" as string | null }, setDraftChatId: jest.fn(),
      prepareDraftChat: jest.fn(),
    };
    let creatingDuringPrepare: boolean | null = null;
    draft.prepareDraftChat.mockImplementation(async () => {
      creatingDuringPrepare = draft.creatingRef.current;
      return "new-1";
    });
    const { submit, options } = await setup({ chatId: null, draft: draft as never });
    await submit({ prompt: "cat", userMessage: "Draw a cat" });
    expect(draft.prepareDraftChat).toHaveBeenCalledWith("free-chat");
    expect(creatingDuringPrepare).toBe(true);
    expect(draft.creatingRef.current).toBe(false);
    expect(draft.skipLoadForChatIdRef.current).toBe("new-1");
    expect(draft.draftChatIdRef.current).toBeNull();
    expect(options.setChatTitle).toHaveBeenCalledWith(null);
    expect(options.setChatId).toHaveBeenCalledWith("new-1");
    expect(draft.setDraftChatId).toHaveBeenCalledWith(null);
    expect((options.router as unknown as { setParams: jest.Mock }).setParams).toHaveBeenCalledWith({ chatId: "new-1" });
    expect(api.generateImage).toHaveBeenCalledWith("tok", expect.objectContaining({ chat_id: "new-1" }), expect.anything());
  });

  it("fails the turn when no chat can be created", async () => {
    const draft = {
      creatingRef: { current: false }, skipLoadForChatIdRef: { current: null }, draftChatIdRef: { current: null },
      setDraftChatId: jest.fn(), prepareDraftChat: jest.fn().mockResolvedValue(null),
    };
    const { submit, replay, options } = await setup({ chatId: null, draft: draft as never });
    await submit({ prompt: "cat", userMessage: "Draw a cat" });
    expect(api.generateImage).not.toHaveBeenCalled();
    expect(options.setChatId).not.toHaveBeenCalled();
    expect(draft.creatingRef.current).toBe(false);
    expect(replay().at(-1)).toMatchObject({ id: "image-gen-failed", image_gen_failure: "failed", image_gen_error: "Could not create chat" });
  });

  it("sends known reference ids without uploading", async () => {
    const { submit } = await setup();
    await submit({ prompt: "cat, blue", userMessage: "make it blue", aspectRatio: "1:1", referenceAttachmentIds: ["ref-1"] });
    expect(uploadChatAttachment).not.toHaveBeenCalled();
    expect(api.generateImage).toHaveBeenCalledWith("tok", {
      chat_id: "chat",
      prompt: "cat, blue",
      user_message: "make it blue",
      aspect_ratio: "1:1",
      reference_attachment_ids: ["ref-1"],
    }, { signal: expect.any(Object) });
  });

  it("uploads a reference photo once and generates from it", async () => {
    (uploadChatAttachment as jest.Mock).mockResolvedValue("uploaded-1");
    const reference = { localUri: "file:///r.png", kind: "image", contentType: "image/png", fileName: "r.png" } satisfies PendingAttachment;
    const { submit } = await setup();
    await submit({ prompt: "make it blue", userMessage: "make it blue", referenceAttachment: reference });
    expect(uploadChatAttachment).toHaveBeenCalledWith("tok", reference);
    expect(api.generateImage).toHaveBeenCalledWith("tok", expect.objectContaining({ reference_attachment_ids: ["uploaded-1"] }), expect.anything());
  });

  it("fails the turn and keeps it for retry when the upload fails", async () => {
    (uploadChatAttachment as jest.Mock).mockRejectedValueOnce(new Error("Could not read the selected file."));
    const reference = { localUri: "file:///r.png", kind: "image", contentType: "image/png", fileName: "r.png" } satisfies PendingAttachment;
    const { submit, replay, result } = await setup();
    await submit({ prompt: "make it blue", userMessage: "make it blue", referenceAttachment: reference });
    expect(api.generateImage).not.toHaveBeenCalled();
    expect(replay().at(-1)).toMatchObject({ image_gen_failure: "failed", image_gen_error: "Could not read the selected file." });
    (uploadChatAttachment as jest.Mock).mockResolvedValueOnce("uploaded-2");
    await act(async () => { result.current.retry(); await Promise.resolve(); await Promise.resolve(); });
    expect(uploadChatAttachment).toHaveBeenCalledTimes(2);
    expect(replay().map((row) => row.id)).toEqual(["saved-user", "saved-image"]);
  });

  it("settles a success: gallery refreshed, scrolled, nothing left to retry", async () => {
    const { submit, options, result } = await setup();
    await submit({ prompt: "cat", userMessage: "Draw a cat" });
    expect(invalidateGalleryCache).toHaveBeenCalledTimes(1);
    expect(options.onScrollToLatest).toHaveBeenCalledTimes(2);
    await act(async () => { result.current.retry(); });
    expect(api.generateImage).toHaveBeenCalledTimes(1);
  });

  it.each([true, false])("opens the upgrade on a 403 (isPaid %p: the server decides)", async (isPaid) => {
    (api.generateImage as jest.Mock).mockRejectedValueOnce(new ApiRequestError(403, "Pro only"));
    const { submit, replay, options } = await setup({ isPaid });
    await submit({ prompt: "cat", userMessage: "Draw a cat" });
    expect(options.onOpenUpgrade).toHaveBeenCalledTimes(1);
    expect(replay().at(-1)).toMatchObject({ id: "image-gen-failed", image_gen_failure: "failed", image_gen_error: undefined });
  });

  it.each([
    [true, "chat.quota_exceeded_pro"],
    [false, "chat.quota_exceeded_free"],
  ])("names the plan's limit when the quota runs out (isPaid %p)", async (isPaid, message) => {
    (api.generateImage as jest.Mock).mockRejectedValueOnce(new ApiRequestError(429, "You've reached today's limit"));
    const { submit, replay, options } = await setup({ isPaid });
    await submit({ prompt: "cat", userMessage: "Draw a cat" });
    expect(options.onOpenUpgrade).not.toHaveBeenCalled();
    expect(replay().at(-1)).toMatchObject({ image_gen_failure: "failed", image_gen_error: message });
  });

  it("retries a failed turn in place", async () => {
    (api.generateImage as jest.Mock).mockRejectedValueOnce(new Error("boom"));
    const { submit, replay, result, options } = await setup();
    await submit({ prompt: "cat", userMessage: "Draw a cat" });
    expect(replay().map((row) => row.id)).toEqual([expect.stringMatching(/^local-img-/), "image-gen-failed"]);
    await act(async () => { result.current.retry(); await Promise.resolve(); await Promise.resolve(); });
    expect(replay().map((row) => row.id)).toEqual(["saved-user", "saved-image"]);
    expect(options.newMessageCountRef.current).toBe(2);
  });
});

describe("image generation under the composer's painted bubble", () => {
  const painted: Message = {
    id: "local-1", role: "user", content: "draw me a cat", model: null, created_at: "now",
    local_image_uri: "file:///reference.png",
  };
  const saved = {
    user_message: { id: "saved-user", role: "user", content: "draw me a cat" },
    assistant_message: { id: "saved-image", role: "assistant", content: "image" },
  };
  beforeEach(() => {
    jest.clearAllMocks();
    (api.generateImage as jest.Mock).mockResolvedValue(saved);
  });

  /** The composer painted its bubble (and counted it) before handing the request over. */
  async function setup(overrides: Partial<Parameters<typeof useImageGeneration>[0]> = {}) {
    const updates: React.SetStateAction<Message[]>[] = [[painted]];
    const count = { current: 1 };
    const options = {
      token: "tok" as string | null, chatId: "chat" as string | null, setChatId: jest.fn(), setChatTitle: jest.fn(),
      setMessages: (update: React.SetStateAction<Message[]>) => { updates.push(update); },
      draft: {} as never, router: { setParams: jest.fn() } as never, selectedModel: "free-chat", streaming: false,
      isPaid: true, isOffline: false, onOpenUpgrade: jest.fn(), onOfflineBlocked: jest.fn(), onScrollToLatest: jest.fn(),
      newMessageCountRef: count, t: (key: string) => key,
      ...overrides,
    };
    const rendered = await renderHook(() => useImageGeneration(options));
    const replay = () => updates.reduce<Message[]>((rows, update) => typeof update === "function" ? update(rows) : update, []);
    return { ...rendered, count, replay };
  }

  it("draws under that bubble instead of adding a second one", async () => {
    let finish!: (value: typeof saved) => void;
    (api.generateImage as jest.Mock).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
    const { result, replay, count } = await setup();
    let pending!: Promise<void>;
    await act(async () => {
      pending = result.current.submitPrompt({ prompt: "cat", userMessage: "draw me a cat", userMessageId: "local-1" });
    });
    expect(replay()).toEqual([
      { ...painted, content: "draw me a cat" },
      expect.objectContaining({ id: "image-gen-pending" }),
    ]);
    expect(count.current).toBe(2);
    await act(async () => { finish(saved); await pending; });
    expect(replay().map((row) => row.id)).toEqual(["saved-user", "saved-image"]);
  });

  it("is not refused by a chat reply that ended in the same tick", async () => {
    const { result, replay } = await setup({ streaming: true });
    await act(async () => {
      await result.current.submitPrompt({ prompt: "cat", userMessage: "draw me a cat", userMessageId: "local-1" });
    });
    expect(reportRecoverableError).not.toHaveBeenCalled();
    expect(replay().map((row) => row.id)).toEqual(["saved-user", "saved-image"]);
  });

  it.each([
    ["offline", { isOffline: true }],
    ["signed out", { token: null }],
  ])("takes the bubble away and gives the draft back when it cannot start (%s)", async (_label, overrides) => {
    const onPersistenceFailure = jest.fn();
    const { result, replay, count } = await setup(overrides);
    await act(async () => {
      await result.current.submitPrompt({
        prompt: "cat", userMessage: "draw me a cat", userMessageId: "local-1", onPersistenceFailure,
      });
    });
    expect(replay()).toEqual([]);
    expect(count.current).toBe(0);
    expect(onPersistenceFailure).toHaveBeenCalledTimes(1);
    expect(api.generateImage).not.toHaveBeenCalled();
  });

  it("takes the bubble and the pending picture away when the drafts fail to save", async () => {
    const onPersistenceFailure = jest.fn();
    const { result, replay, count } = await setup();
    await act(async () => {
      await result.current.submitPrompt({
        prompt: "cat", userMessage: "draw me a cat", userMessageId: "local-1",
        persistenceReady: Promise.resolve(false), onPersistenceFailure,
      });
    });
    expect(replay()).toEqual([]);
    expect(count.current).toBe(0);
    expect(onPersistenceFailure).toHaveBeenCalledTimes(1);
  });

  it("retries a failed picture under the same bubble", async () => {
    (api.generateImage as jest.Mock).mockRejectedValueOnce(new Error("boom"));
    const { result, replay } = await setup();
    await act(async () => {
      await result.current.submitPrompt({ prompt: "cat", userMessage: "draw me a cat", userMessageId: "local-1" });
    });
    expect(replay().map((row) => row.id)).toEqual(["local-1", "image-gen-failed"]);
    await act(async () => { result.current.retry(); await Promise.resolve(); await Promise.resolve(); });
    expect(replay().map((row) => row.id)).toEqual(["saved-user", "saved-image"]);
    expect(api.generateImage).toHaveBeenCalledTimes(2);
  });
});
