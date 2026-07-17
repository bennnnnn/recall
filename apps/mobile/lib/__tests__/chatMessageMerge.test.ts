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

  it("transfers local_image_uri when optimistic local-* id becomes a server UUID", () => {
    const previous: Message[] = [
      {
        id: "local-1",
        role: "user",
        content: "Solve the math problem in this image step by step.",
        model: null,
        local_image_uri: "file:///tmp/scan.jpg",
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "streamed-1",
        role: "assistant",
        content: "x = 2",
        model: null,
        created_at: "2026-01-01T00:00:01Z",
      },
    ];
    const incoming: Message[] = [
      {
        id: "11111111-1111-1111-1111-111111111111",
        role: "user",
        content:
          "[Image: 22222222-2222-2222-2222-222222222222]\n\nSolve the math problem in this image step by step.",
        model: null,
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "33333333-3333-3333-3333-333333333333",
        role: "assistant",
        content: "x = 2",
        model: null,
        created_at: "2026-01-01T00:00:01Z",
      },
    ];
    const merged = mergeLocalAttachmentUris(previous, incoming);
    expect(merged[0].local_image_uri).toBe("file:///tmp/scan.jpg");
    expect(merged[1].local_image_uri).toBeFalsy();
  });

  it("transfers local file preview when local-* id becomes a server UUID", () => {
    const previous: Message[] = [
      {
        id: "local-file",
        role: "user",
        content: "notes.pdf",
        model: null,
        local_file_uri: "file:///tmp/notes.pdf",
        local_file_name: "notes.pdf",
        local_file_content_type: "application/pdf",
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    const incoming: Message[] = [
      {
        id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        role: "user",
        content: "[File: bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb]\n\nSummarize this file.",
        model: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    const merged = mergeLocalAttachmentUris(previous, incoming);
    expect(merged[0].local_file_uri).toBe("file:///tmp/notes.pdf");
    expect(merged[0].local_file_name).toBe("notes.pdf");
    expect(merged[0].local_file_content_type).toBe("application/pdf");
  });
});
