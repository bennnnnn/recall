import { requestRaw } from "@/lib/api/client";
import { File } from "expo-file-system";
import { fetchAttachmentBytes } from "@/lib/fetchAttachmentBytes";

jest.mock("@/lib/api/client", () => ({
  apiUrl: (path: string) => `https://api.test/v1${path}`,
  requestRaw: jest.fn(),
}));

const mockFileRead = jest.fn();
let mockGeneration = 0;
jest.mock("expo-file-system", () => ({ File: jest.fn() }));
jest.mock("@/lib/config", () => ({ getApiUrl: () => "https://api.test/v1" }));
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => mockGeneration,
  requireTokenSession: jest.fn(),
  SessionChangedError: class extends Error { constructor() { super("Session changed"); } },
}));
const mockFetch = jest.fn();
const originalFetch = globalThis.fetch;
globalThis.fetch = mockFetch as unknown as typeof fetch;
const rawMock = requestRaw as jest.MockedFunction<typeof requestRaw>;
const bytes = new Uint8Array([1, 2, 3]).buffer;

beforeEach(() => {
  mockFetch.mockReset();
  rawMock.mockReset();
  mockGeneration = 0;
  mockFileRead.mockReset().mockResolvedValue(bytes);
  jest.mocked(File).mockImplementation(() => ({ arrayBuffer: mockFileRead }) as unknown as File);
});
afterAll(() => { globalThis.fetch = originalFetch; });

it("uses the shared authenticated request boundary for Recall attachments", async () => {
  rawMock.mockResolvedValueOnce({ ok: true, arrayBuffer: async () => bytes } as Response);
  await expect(fetchAttachmentBytes("https://api.test/v1/attachments/abc/file?download=1", "access"))
    .resolves.toBe(bytes);
  expect(rawMock).toHaveBeenCalledWith("/attachments/abc/file?download=1", "access");
  expect(mockFetch).not.toHaveBeenCalled();
});

it.each([
  "https://external.test/v1/attachments/abc/file",
  "https://api.test.external.test/v1/attachments/abc/file",
  "https://api.test/v1-other/attachments/abc/file",
  "https://api.test/attachments/abc/file",
])("never sends credentials to a non-API attachment URI: %s", async (uri) => {
  mockFetch.mockResolvedValueOnce({ ok: true, arrayBuffer: async () => bytes } as Response);
  await expect(fetchAttachmentBytes(uri, "access")).resolves.toBe(bytes);
  expect(mockFetch).toHaveBeenCalledWith(uri);
  expect(rawMock).not.toHaveBeenCalled();
});

it("surfaces rejected authorization without a separate signout or refresh flow", async () => {
  rawMock.mockResolvedValueOnce({ ok: false, status: 401 } as Response);
  await expect(fetchAttachmentBytes("https://api.test/v1/attachments/abc/file", "access"))
    .rejects.toThrow("Could not load attachment");
  expect(rawMock).toHaveBeenCalledTimes(1);
  expect(mockFetch).not.toHaveBeenCalled();
});


it.each(["file:///local.pdf", "content://picked/document/1"])("reads native URI via Expo File: %s", async (uri) => {
  await expect(fetchAttachmentBytes(uri, "access")).resolves.toBe(bytes);
  expect(mockFileRead).toHaveBeenCalledTimes(1);
  expect(mockFetch).not.toHaveBeenCalled();
});

it("rejects an attachment body that finishes after account change", async () => {
  rawMock.mockResolvedValueOnce({ ok: true, arrayBuffer: async () => { mockGeneration++; return bytes; } } as Response);
  await expect(fetchAttachmentBytes("https://api.test/v1/attachments/abc/file", "access"))
    .rejects.toThrow("Session changed");
});
