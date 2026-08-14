import { notifyUnauthorized, refreshAccessToken } from "@/lib/api/client";
import { fetchAttachmentBytes } from "@/lib/fetchAttachmentBytes";

jest.mock("@/lib/api/client", () => ({
  refreshAccessToken: jest.fn(),
  notifyUnauthorized: jest.fn(),
}));

const mockFetch = jest.fn();
const originalFetch = globalThis.fetch;
globalThis.fetch = mockFetch as unknown as typeof fetch;

const refreshMock = refreshAccessToken as jest.MockedFunction<typeof refreshAccessToken>;
const unauthorizedMock = notifyUnauthorized as jest.MockedFunction<typeof notifyUnauthorized>;

describe("fetchAttachmentBytes", () => {
  const attachmentUri = "http://test.local/attachments/abc/file";

  beforeEach(() => {
    mockFetch.mockReset();
    refreshMock.mockReset();
    unauthorizedMock.mockReset();
  });

  afterAll(() => {
    globalThis.fetch = originalFetch;
  });

  it("retries once via refreshAccessToken on 401", async () => {
    const bytes = new Uint8Array([1, 2, 3]).buffer;
    mockFetch
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        arrayBuffer: async () => bytes,
      } as Response);
    refreshMock.mockResolvedValue("fresh-token");

    await expect(fetchAttachmentBytes(attachmentUri, "stale-token")).resolves.toBe(bytes);
    expect(refreshMock).toHaveBeenCalledTimes(1);
    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(mockFetch.mock.calls[1][1]).toEqual({
      headers: { Authorization: "Bearer fresh-token" },
    });
    expect(unauthorizedMock).not.toHaveBeenCalled();
  });

  it("notifies unauthorized and throws when refresh fails", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 401 } as Response);
    refreshMock.mockResolvedValue(null);

    await expect(fetchAttachmentBytes(attachmentUri, "stale-token")).rejects.toThrow(
      "Could not load attachment.",
    );
    expect(unauthorizedMock).toHaveBeenCalledTimes(1);
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("does not attach a bearer token or refresh for non-attachment URIs", async () => {
    const bytes = new Uint8Array([9]).buffer;
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      arrayBuffer: async () => bytes,
    } as Response);

    await expect(fetchAttachmentBytes("file:///local.pdf", "tok")).resolves.toBe(bytes);
    expect(mockFetch.mock.calls[0][1]).toEqual({ headers: {} });
    expect(refreshMock).not.toHaveBeenCalled();
  });
});
