import { mergeLocalAttachmentUris } from "@/lib/chat/chatMessageMerge";
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

  it("M11: preserves streamed-* assistant when server list has no assistant row", () => {
    const previous: Message[] = [
      {
        id: "u1",
        role: "user",
        content: "hi",
        model: null,
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "streamed-100",
        role: "assistant",
        content: "Hello!",
        model: "free-chat",
        created_at: "2026-01-01T00:00:01Z",
      },
    ];
    const incoming: Message[] = [
      {
        id: "u1",
        role: "user",
        content: "hi",
        model: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    const merged = mergeLocalAttachmentUris(previous, incoming);
    expect(merged).toHaveLength(2);
    expect(merged[1].id).toBe("streamed-100");
    expect(merged[1].content).toBe("Hello!");
  });

  it("M11: drops streamed-* assistant when server list has a persisted assistant", () => {
    const previous: Message[] = [
      {
        id: "u1",
        role: "user",
        content: "hi",
        model: null,
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "streamed-100",
        role: "assistant",
        content: "Hello!",
        model: "free-chat",
        created_at: "2026-01-01T00:00:01Z",
      },
    ];
    const incoming: Message[] = [
      {
        id: "u1",
        role: "user",
        content: "hi",
        model: null,
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        role: "assistant",
        content: "Hello!",
        model: "free-chat",
        created_at: "2026-01-01T00:00:01Z",
      },
    ];
    const merged = mergeLocalAttachmentUris(previous, incoming);
    expect(merged).toHaveLength(2);
    expect(merged[1].id).toBe("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
  });

  it("keeps the second turn's partial reply while only its user row is persisted", () => {
    const make = (id: string, role: "user" | "assistant", content: string): Message => ({
      id, role, content, model: null, created_at: "2026-01-01T00:00:00Z",
    });
    const firstTurn = [make("u1", "user", "First"), make("a1", "assistant", "First answer")];
    const user = make("u2", "user", "Second");
    const partial = make("streamed-200", "assistant", "Second answer so far");
    const previous = [...firstTurn, user, partial];
    const incoming = [...firstTurn, user];

    expect(mergeLocalAttachmentUris(previous, incoming)).toEqual(previous);
    const complete = make("a2", "assistant", "Second answer complete");
    expect(mergeLocalAttachmentUris(previous, [...incoming, complete])).toEqual([...incoming, complete]);
  });

  it("does not carry an earlier partial into a newer unanswered turn", () => {
    const make = (id: string, role: "user" | "assistant"): Message => ({
      id, role, content: id, model: null, created_at: "2026-01-01T00:00:00Z",
    });
    const firstUser = make("u1", "user");
    const latestUser = make("u2", "user");
    const previous = [firstUser, make("streamed-100", "assistant"), latestUser];
    const incoming = [firstUser, latestUser];
    expect(mergeLocalAttachmentUris(previous, incoming)).toEqual(incoming);
  });

});
