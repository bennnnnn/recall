import { mergeLocalAttachmentUris } from "@/lib/chatMessageMerge";
import type { Message } from "@/lib/api";

describe("mergeLocalAttachmentUris", () => {
  it("preserves local_image_uri from the prior optimistic bubble", () => {
    const previous: Message[] = [
      {
        id: "m1",
        role: "user",
        content: "[Image: /attachments/abc/file]",
        model: null,
        local_image_uri: "file:///tmp/photo.jpg",
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    const incoming: Message[] = [
      {
        id: "m1",
        role: "user",
        content: "[Image: /attachments/abc/file]",
        model: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    const merged = mergeLocalAttachmentUris(previous, incoming);
    expect(merged[0].local_image_uri).toBe("file:///tmp/photo.jpg");
  });
});
