import { requestRaw } from "@/lib/api/client";
import { fetchAttachmentBytes } from "@/lib/fetchAttachmentBytes";

jest.mock("@/lib/api/client", () => ({
  apiUrl: (path: string) => `https://api.test/v1${path}`,
  requestRaw: jest.fn(),
}));

const mockFetch = jest.fn();
const originalFetch = globalThis.fetch;
globalThis.fetch = mockFetch as unknown as typeof fetch;
const rawMock = requestRaw as jest.MockedFunction<typeof requestRaw>;
const bytes = new Uint8Array([1, 2, 3]).buffer;

beforeEach(() => {
  mockFetch.mockReset();
  rawMock.mockReset();
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
  "file:///local.pdf",
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
