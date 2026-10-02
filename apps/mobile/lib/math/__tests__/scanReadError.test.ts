import { ApiRequestError } from "@/lib/api/client";
import { mathScanFailureDetail } from "@/lib/math/scanReadError";

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

describe("mathScanFailureDetail", () => {
  it("keeps the rate-limit and size details", () => {
    expect(
      mathScanFailureDetail(
        new ApiRequestError(429, JSON.stringify({ detail: "Too many scans in a row. Try again in a few minutes." })),
      ),
    ).toBe("Too many scans in a row. Try again in a few minutes.");
    expect(
      mathScanFailureDetail(new ApiRequestError(413, JSON.stringify({ detail: "Image too large" }))),
    ).toBe("Image too large");
  });

  it("stays quiet for a network failure and any other status", () => {
    expect(mathScanFailureDetail(new Error("offline"))).toBeNull();
    expect(mathScanFailureDetail(new ApiRequestError(500, JSON.stringify({ detail: "nope" })))).toBeNull();
    expect(mathScanFailureDetail(new ApiRequestError(429, "not json"))).toBeNull();
  });
});
