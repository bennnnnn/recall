jest.mock("@/features/attachments/model/attachments", () => ({
  messageTextForSend: (text: string, attached?: { kind: string; fileName?: string } | null) => {
    const trimmed = text.trim();
    if (trimmed) return trimmed;
    if (attached?.kind === "file") return "Summarize this file.";
    return "";
  },
}));

import {
  buildOptimisticUserMessage,
  buildPendingSendAfterCreate,
  shouldBlockSend,
} from "@/features/chat/model/sendLogic";

describe("chatSendLogic", () => {
  it("shouldBlockSend rejects empty sends and busy states", () => {
    expect(
      shouldBlockSend({
        text: "",
        hasAttachment: false,
        streaming: false,
        token: "tok",
        creating: false,
        attachPicking: false,
        isOffline: false,
      }),
    ).toBe(true);
    expect(
      shouldBlockSend({
        text: "Hi",
        hasAttachment: false,
        streaming: true,
        token: "tok",
        creating: false,
        attachPicking: false,
        isOffline: false,
      }),
    ).toBe(true);
    expect(
      shouldBlockSend({
        text: "Hi",
        hasAttachment: false,
        streaming: false,
        token: null,
        creating: false,
        attachPicking: false,
        isOffline: false,
      }),
    ).toBe(true);
    expect(
      shouldBlockSend({
        text: "Hi",
        hasAttachment: false,
        streaming: false,
        token: "tok",
        creating: true,
        attachPicking: false,
        isOffline: false,
      }),
    ).toBe(true);
    expect(
      shouldBlockSend({
        text: "",
        hasAttachment: true,
        streaming: false,
        token: "tok",
        creating: false,
        attachPicking: false,
        isOffline: false,
      }),
    ).toBe(false);
    expect(
      shouldBlockSend({
        text: "Hello",
        hasAttachment: false,
        streaming: false,
        token: "tok",
        creating: false,
        attachPicking: false,
        isOffline: false,
      }),
    ).toBe(false);
  });

  it("shouldBlockSend blocks sends while offline even with valid text", () => {
    expect(
      shouldBlockSend({
        text: "Hello",
        hasAttachment: false,
        streaming: false,
        token: "tok",
        creating: false,
        attachPicking: false,
        isOffline: true,
      }),
    ).toBe(true);
    expect(
      shouldBlockSend({
        text: "",
        hasAttachment: true,
        streaming: false,
        token: "tok",
        creating: false,
        attachPicking: false,
        isOffline: true,
      }),
    ).toBe(true);
  });

  it("buildOptimisticUserMessage uses file name when caption empty", () => {
    const msg = buildOptimisticUserMessage({
      text: "",
      attached: {
        kind: "file",
        fileName: "notes.pdf",
        contentType: "application/pdf",
        localUri: "file:///notes.pdf",
      },
      optimisticId: "local-1",
      createdAt: "2026-01-01T00:00:00.000Z",
    });
    expect(msg.content).toBe("notes.pdf");
    expect(msg.role).toBe("user");
    expect(msg.local_image_uri).toBeNull();
    expect(msg.created_at).toBe("2026-01-01T00:00:00.000Z");
  });

  it("buildPendingSendAfterCreate marks skipUserBubble and image uri", () => {
    const pending = buildPendingSendAfterCreate({
      text: "Look",
      attached: {
        kind: "image",
        localUri: "file:///photo.jpg",
        contentType: "image/jpeg",
        fileName: "photo.jpg",
      },
      attachmentIds: ["att-1"],
      optimisticId: "local-1",
      model: "smart-chat",
    });
    expect(pending.skipUserBubble).toBe(true);
    expect(pending.trackSendingMessageId).toBe("local-1");
    expect(pending.attachmentIds).toEqual(["att-1"]);
    expect(pending.localImageUri).toBe("file:///photo.jpg");
    expect(pending.text).toContain("Look");
    expect(pending.model).toBe("smart-chat");
  });

  it("draws a paste sent alone as its chip, never as the file's name", () => {
    const pasted = {
      kind: "file" as const,
      localUri: "file:///cache/PastedText/paste-1.txt",
      contentType: "text/plain",
      fileName: "pasted-text.txt",
      pasted: { chars: 3000, preview: "p" },
    };
    const alone = buildOptimisticUserMessage({ text: "", attached: pasted, optimisticId: "o1", createdAt: "now" });
    expect(alone.content).toBe("");
    expect(alone.local_file_name).toBe("pasted-text.txt");
    const asked = buildOptimisticUserMessage({ text: " Tidy this ", attached: pasted, optimisticId: "o2", createdAt: "now" });
    expect(asked.content).toBe("Tidy this");
    const picked = { ...pasted, fileName: "notes.txt", pasted: undefined };
    expect(buildOptimisticUserMessage({ text: "", attached: picked, optimisticId: "o3", createdAt: "now" }).content).toBe(
      "notes.txt",
    );
    // A picked file named as a paste is a document: it asks what a file asks.
    const named = { ...pasted, pasted: undefined };
    expect(buildOptimisticUserMessage({ text: "", attached: named, optimisticId: "o4", createdAt: "now" }).content).toBe(
      "pasted-text.txt",
    );
  });
});
