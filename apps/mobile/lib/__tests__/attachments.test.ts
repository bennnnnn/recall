import { File } from "expo-file-system";
import { api } from "@/lib/api";
import { requestRaw } from "@/lib/api/client";
import { pickDocument, pickFromPhotoLibrary, uploadChatAttachment } from "@/lib/attachments";
import * as DocumentPicker from "expo-document-picker";
import * as ImagePicker from "expo-image-picker";
import * as ImageManipulator from "expo-image-manipulator";

const mockRead = jest.fn();
let mockGeneration = 0;
jest.mock("expo-file-system", () => ({ File: jest.fn() }));
jest.mock("expo-file-system/legacy", () => ({ getInfoAsync: jest.fn(async () => ({ exists: true, size: 3 })) }));
jest.mock("expo-document-picker", () => ({ getDocumentAsync: jest.fn() }));
jest.mock("expo-image-picker", () => ({
  requestMediaLibraryPermissionsAsync: jest.fn(async () => ({ granted: true })),
  launchImageLibraryAsync: jest.fn(),
}));
jest.mock("expo-image-manipulator", () => ({
  SaveFormat: { JPEG: "jpeg" }, manipulateAsync: jest.fn(async () => ({ uri: "file:///converted.jpg" })),
}));
jest.mock("@/lib/api", () => ({ api: {
  presignAttachment: jest.fn(), confirmAttachment: jest.fn(), cancelAttachment: jest.fn(),
} }));
jest.mock("@/lib/api/client", () => ({ requestRaw: jest.fn() }));
jest.mock("@/lib/config", () => ({ getApiUrl: () => "https://api.test" }));
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => mockGeneration,
  requireTokenSession: jest.fn(),
  SessionChangedError: class extends Error { constructor() { super("Session changed"); } },
}));
jest.mock("@/lib/cache/galleryListCache", () => ({ invalidateGalleryCache: jest.fn() }));

const mockFetch = jest.fn();
const originalFetch = globalThis.fetch;
const pending = { localUri: "file:///picked.pdf", contentType: "application/pdf", fileName: "picked.pdf", kind: "file" as const };
beforeEach(() => {
  jest.clearAllMocks();
  mockGeneration = 0;
  mockFetch.mockReset().mockResolvedValue({ ok: true, arrayBuffer: async () => new Uint8Array([1, 2, 3]).buffer });
  mockRead.mockReset().mockResolvedValue(new Uint8Array([1, 2, 3]).buffer);
  jest.mocked(File).mockImplementation(() => ({ exists: true, size: 3, arrayBuffer: mockRead }) as unknown as File);
  jest.mocked(api.presignAttachment).mockResolvedValue({ attachment_id: "a1", upload_url: "/ignored", api_upload: true, storage_key: "key", headers: {} });
  jest.mocked(requestRaw).mockResolvedValue({ ok: true } as Response);
  globalThis.fetch = mockFetch as unknown as typeof fetch;
});
afterAll(() => { globalThis.fetch = originalFetch; });

it("reads picked native files with Expo File and uploads API bytes through refresh-aware requestRaw", async () => {
  await expect(uploadChatAttachment("token", pending)).resolves.toBe("a1");
  expect(mockRead).toHaveBeenCalledTimes(1);
  expect(requestRaw).toHaveBeenCalledWith("/attachments/a1/upload", "token", expect.objectContaining({ method: "PUT", body: expect.any(ArrayBuffer) }), true, expect.any(Number));
  expect(mockFetch).not.toHaveBeenCalled();
});

it("never adds Recall authorization to a storage URL sharing only the API host prefix", async () => {
  jest.mocked(api.presignAttachment).mockResolvedValue({ attachment_id: "a1", upload_url: "https://api.test.external.test/upload", api_upload: false, storage_key: "key", headers: {} });
  await uploadChatAttachment("token", pending);
  const remote = mockFetch.mock.calls.find(([url]) => url === "https://api.test.external.test/upload");
  expect(remote?.[1].headers).not.toHaveProperty("Authorization");
  expect(api.confirmAttachment).toHaveBeenCalledWith("token", "a1");
});

it("does not continue an upload after account change during native file reading", async () => {
  mockRead.mockImplementationOnce(async () => { mockGeneration++; return new ArrayBuffer(3); });
  await expect(uploadChatAttachment("token", pending)).rejects.toThrow("Session changed");
  expect(requestRaw).not.toHaveBeenCalled();
  expect(mockFetch).not.toHaveBeenCalled();
});

it("does not upload changed bytes with a stale presigned size", async () => {
  mockRead.mockResolvedValueOnce(new ArrayBuffer(9));
  await expect(uploadChatAttachment("token", pending)).rejects.toThrow(/changed|size/i);
  expect(requestRaw).not.toHaveBeenCalled();
});

it("keeps cleanup best effort when an upload fails", async () => {
  jest.mocked(requestRaw).mockRejectedValueOnce(new Error("Upload offline"));
  jest.mocked(api.cancelAttachment).mockRejectedValueOnce(new Error("Cleanup offline"));
  await expect(uploadChatAttachment("token", pending)).rejects.toThrow("Upload offline");
  expect(api.cancelAttachment).toHaveBeenCalledWith("token", "a1");
});

it("converts a HEIC photo when the picker omits MIME metadata", async () => {
  jest.mocked(ImagePicker.launchImageLibraryAsync).mockResolvedValue({ canceled: false, assets: [{ uri: "file:///photo.HEIC", fileName: "photo.HEIC", width: 10, height: 10 }] });
  await expect(pickFromPhotoLibrary()).resolves.toMatchObject({ contentType: "image/jpeg", localUri: "file:///converted.jpg" });
  expect(ImageManipulator.manipulateAsync).toHaveBeenCalled();
});

it("does not classify unknown document types as JPEG photos", async () => {
  jest.mocked(DocumentPicker.getDocumentAsync).mockResolvedValue({ canceled: false, assets: [{ uri: "file:///archive.bin", name: "archive.bin", lastModified: 0 }] });
  await expect(pickDocument()).resolves.toMatchObject({ contentType: "application/octet-stream", kind: "file" });
});
