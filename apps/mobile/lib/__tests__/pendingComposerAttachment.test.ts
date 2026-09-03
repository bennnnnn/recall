import {
  queueComposerAttachment,
  resetComposerAttachmentQueue,
  subscribeComposerAttachmentQueue,
  takeQueuedComposerAttachment,
} from "@/lib/pendingComposerAttachment";

describe("pendingComposerAttachment", () => {
  afterEach(() => {
    resetComposerAttachmentQueue();
  });

  it("hands the pick to a subscriber and clears after take", () => {
    const pending = {
      localUri: "file://a.jpg",
      contentType: "image/jpeg",
      fileName: "a.jpg",
      kind: "image" as const,
      existingAttachmentId: "att-1",
    };
    const listener = jest.fn();
    const stop = subscribeComposerAttachmentQueue(listener);
    queueComposerAttachment(pending);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(takeQueuedComposerAttachment()).toEqual(pending);
    expect(takeQueuedComposerAttachment()).toBeNull();
    stop();
  });
});
