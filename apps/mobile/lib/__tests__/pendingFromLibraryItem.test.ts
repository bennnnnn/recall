jest.mock("@/lib/downloadChatAttachment", () => ({
  ensureLocalAttachmentFile: jest.fn(async ({ uri }: { uri: string }) => `file://cache/${uri}`),
}));

jest.mock("@/lib/attachmentUri", () => ({
  resolveAttachmentUri: ({ attachmentId }: { attachmentId: string }) =>
    `http://api.test/attachments/${attachmentId}/file`,
}));

import { ensureLocalAttachmentFile } from "@/lib/downloadChatAttachment";
import { pendingFromLibraryItem } from "@/lib/pendingFromLibraryItem";

describe("pendingFromLibraryItem", () => {
  it("downloads images and skips re-upload via existingAttachmentId", async () => {
    const pending = await pendingFromLibraryItem(
      {
        id: "img-1",
        content_type: "image/png",
        original_filename: "cat.png",
        download_url: "/attachments/img-1/file",
      },
      "tok",
    );

    expect(ensureLocalAttachmentFile).toHaveBeenCalled();
    expect(pending).toMatchObject({
      kind: "image",
      fileName: "cat.png",
      existingAttachmentId: "img-1",
    });
  });

  it("does not download files for the composer chip", async () => {
    (ensureLocalAttachmentFile as jest.Mock).mockClear();
    const pending = await pendingFromLibraryItem(
      {
        id: "doc-1",
        content_type: "application/pdf",
        original_filename: "notes.pdf",
        download_url: "/attachments/doc-1/file",
      },
      "tok",
    );

    expect(ensureLocalAttachmentFile).not.toHaveBeenCalled();
    expect(pending).toMatchObject({
      kind: "file",
      fileName: "notes.pdf",
      existingAttachmentId: "doc-1",
    });
  });
});
