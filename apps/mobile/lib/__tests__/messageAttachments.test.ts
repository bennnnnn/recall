import { parseUserMessageContent, isPdfContentType } from "@/lib/messageAttachments";

describe("messageAttachments", () => {
  it("parses pdf file marker with attachment id", () => {
    const parsed = parseUserMessageContent(
      "Summarize this\n\n[File: /attachments/550e8400-e29b-41d4-a716-446655440000/file]\n[File (application/pdf)]\nPage one text",
    );
    expect(parsed.files).toHaveLength(1);
    expect(parsed.files[0].attachmentId).toBe("550e8400-e29b-41d4-a716-446655440000");
    expect(isPdfContentType(parsed.files[0].contentType)).toBe(true);
    expect(parsed.caption).toBe("Summarize this");
  });

  it("strips attachment boilerplate caption for files", () => {
    const parsed = parseUserMessageContent(
      "Summarize this file.\n\n[File: /attachments/550e8400-e29b-41d4-a716-446655440000/file]\n[File attached: application/pdf, 100 bytes]",
    );
    expect(parsed.caption).toBe("");
    expect(parsed.hasFileAttachment).toBe(true);
  });
});
