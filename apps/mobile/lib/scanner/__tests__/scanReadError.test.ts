import { ApiRequestError } from "@/lib/api/client";
import { scanFailureDetail, scanFailureMessageKey } from "@/lib/scanner/scanReadError";

jest.mock("@/lib/config", () => ({
  getApiUrl: () => "http://test.local",
}));
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => 0,
  requireTokenSession: jest.fn(),
  SessionChangedError: class extends Error {},
  getRefreshToken: jest.fn(),
  setTokenPair: jest.fn(),
}));

const refused = (status: number, detail: string) =>
  new ApiRequestError(status, JSON.stringify({ detail }));

describe("scanFailureDetail", () => {
  it.each([
    [404, "Not available"],
    [413, "Image too large"],
    [429, "Too many scans in a row. Try again in a few minutes."],
    [429, "Reading photos is paused for now. Type the problem, or try again later."],
  ])("keeps the detail of a %s", (status, detail) => {
    expect(scanFailureDetail(refused(status, detail))).toBe(detail);
  });

  it("stays generic for anything else", () => {
    expect(scanFailureDetail(new Error("offline"))).toBeNull();
    expect(scanFailureDetail(refused(500, "nope"))).toBeNull();
    expect(scanFailureDetail(refused(400, "Invalid image payload"))).toBeNull();
    expect(scanFailureDetail(new ApiRequestError(429, "not json"))).toBeNull();
    expect(scanFailureDetail(refused(429, "  "))).toBeNull();
  });
});

describe("scanFailureMessageKey", () => {
  it("maps each detail the API sends to a locale key", () => {
    expect(scanFailureMessageKey("Not available")).toBe("chat.scan_unavailable");
    expect(scanFailureMessageKey("Image too large")).toBe("chat.scan_too_large");
    expect(scanFailureMessageKey("Too many scans in a row. Try again in a few minutes.")).toBe(
      "chat.scan_rate_limit",
    );
    expect(
      scanFailureMessageKey("Reading photos is paused for now. Type the problem, or try again later."),
    ).toBe("chat.scan_spend_cap");
    expect(scanFailureMessageKey("something else")).toBeNull();
  });
});
