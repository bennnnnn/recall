import { attachmentRequestHeaders, recallAttachmentPath, resolveAttachmentUri } from "@/lib/attachmentUri";
jest.mock("@/lib/config", () => ({ getApiUrl: () => "https://api.test/v1/" }));

it("builds one canonical API path with a configured base path and trailing slash", () => {
  expect(resolveAttachmentUri({ attachmentId: "abc", width: 300 }))
    .toBe("https://api.test/v1/attachments/abc/file?w=300");
});

it("does not change signed external URLs when a thumbnail width is requested", () => {
  const path = "https://storage.test/image.jpg?signature=original";
  expect(resolveAttachmentUri({ path, width: 300 })).toBe(path);
});

it("replaces an existing API width parameter and preserves URL fragments", () => {
  expect(resolveAttachmentUri({ path: "https://api.test/v1/attachments/a/file?w=100#preview", width: 300 }))
    .toBe("https://api.test/v1/attachments/a/file?w=300#preview");
});

it.each([
  "https://api.test.external.test/v1/attachments/a/file",
  "https://api.test/v1-other/attachments/a/file",
  "https://api.test/attachments/a/file",
  "https://external.test/v1/attachments/a/file",
  "file:///image.jpg",
])("never authorizes non-API image sources: %s", (uri) => {
  expect(recallAttachmentPath(uri)).toBeNull();
  expect(attachmentRequestHeaders(uri, "token")).toEqual({});
});

it("authorizes images only within the configured API attachment route", () => {
  const uri = "https://api.test/v1/attachments/a/file?w=300";
  expect(recallAttachmentPath(uri)).toBe("/attachments/a/file?w=300");
  expect(attachmentRequestHeaders(uri, "token")).toEqual({ Authorization: "Bearer token" });
});
