import { requestRaw } from "@/lib/api/client";
import { File } from "expo-file-system";
import { downloadAttachmentFile, fetchAttachmentBytes } from "@/features/attachments/model/fetchAttachmentBytes";

jest.mock("@/lib/api/client", () => ({
  apiUrl: (path: string) => `https://api.test/v1${path}`,
  requestRaw: jest.fn(),
  // The real one refreshes on 401; here it attaches a fixed token and reports the status.
  authorizeNativeTransfer: jest.fn(async (token: string, send: (h: Record<string, string>) => Promise<number>) =>
    send({ Authorization: `Bearer ${token}` })),
}));

const mockFileRead = jest.fn();
let mockGeneration = 0;
const mockDownloadFile = jest.fn();
jest.mock("expo-file-system", () => ({
  File: Object.assign(jest.fn(), { downloadFileAsync: (...args: unknown[]) => mockDownloadFile(...args) }),
}));
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
  mockDownloadFile.mockReset().mockResolvedValue({});
  jest.mocked(File).mockImplementation((uri?: unknown) => ({ uri, arrayBuffer: mockFileRead }) as unknown as File);
});
afterAll(() => { globalThis.fetch = originalFetch; });

it("uses the shared authenticated request boundary for Recall attachments", async () => {
  rawMock.mockResolvedValueOnce({ ok: true, arrayBuffer: async () => bytes } as Response);
  await expect(fetchAttachmentBytes("https://api.test/v1/attachments/abc/file?download=1", "access"))
    .resolves.toBe(bytes);
  expect(rawMock).toHaveBeenCalledWith("/attachments/abc/file?download=1", "access", { signal: undefined });
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
  expect(mockFetch).toHaveBeenCalledWith(uri, { signal: undefined });
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

it("passes a closed viewer's signal to the request", async () => {
  const controller = new AbortController();
  rawMock.mockResolvedValueOnce({ ok: true, arrayBuffer: async () => bytes } as Response);
  await fetchAttachmentBytes("https://api.test/v1/attachments/abc/file", "access", controller.signal);
  expect(rawMock).toHaveBeenCalledWith("/attachments/abc/file", "access", { signal: controller.signal });
});

describe("downloadAttachmentFile", () => {
  it("downloads a Recall attachment natively with the Bearer header", async () => {
    const controller = new AbortController();
    await downloadAttachmentFile("https://api.test/v1/attachments/abc/file", "file:///cache/att-a.part", "access", controller.signal);
    expect(mockDownloadFile).toHaveBeenCalledWith(
      "https://api.test/v1/attachments/abc/file",
      expect.objectContaining({ uri: "file:///cache/att-a.part" }),
      { headers: { Authorization: "Bearer access" }, idempotent: true, signal: controller.signal },
    );
  });

  it("never sends credentials to another host", async () => {
    await downloadAttachmentFile("https://external.test/v1/attachments/abc/file", "file:///cache/att-b.part", "access");
    expect(mockDownloadFile).toHaveBeenCalledWith(
      "https://external.test/v1/attachments/abc/file",
      expect.anything(),
      expect.objectContaining({ headers: {} }),
    );
  });

  it.each(["Unable to download a file: response has status: 404", "server returned HTTP 500"])(
    "turns a refused download into a plain error: %s",
    async (message) => {
      mockDownloadFile.mockRejectedValueOnce(new Error(message));
      await expect(downloadAttachmentFile("https://api.test/v1/attachments/abc/file", "file:///cache/x", "access"))
        .rejects.toThrow("Could not load attachment.");
    },
  );

  it("rethrows a cancel or network failure as it is", async () => {
    const abort = Object.assign(new Error("aborted"), { name: "AbortError" });
    mockDownloadFile.mockRejectedValueOnce(abort);
    await expect(downloadAttachmentFile("https://api.test/v1/attachments/abc/file", "file:///cache/x", "access"))
      .rejects.toBe(abort);
  });
});
