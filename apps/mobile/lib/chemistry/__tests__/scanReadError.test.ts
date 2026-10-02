import { ApiRequestError } from "@/lib/api/client";

import {
  chemistryScanFailureDetail,
  chemistryScanFailureMessageKey,
} from "@/lib/chemistry/scanReadError";

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

describe("chemistryScanFailureDetail", () => {
  it("keeps the detail for a rate limit and a missing reader", () => {
    expect(
      chemistryScanFailureDetail(
        new ApiRequestError(429, JSON.stringify({ detail: "Too many scans in a row. Try again in a few minutes." })),
      ),
    ).toBe("Too many scans in a row. Try again in a few minutes.");
    expect(
      chemistryScanFailureDetail(new ApiRequestError(404, JSON.stringify({ detail: "Not available" }))),
    ).toBe("Not available");
  });

  it("leaves a network or vision failure unnamed", () => {
    expect(chemistryScanFailureDetail(new Error("offline"))).toBeNull();
    expect(chemistryScanFailureDetail(new ApiRequestError(500, JSON.stringify({ detail: "nope" })))).toBeNull();
    expect(chemistryScanFailureDetail(new ApiRequestError(429, "not json"))).toBeNull();
  });
});

describe("chemistryScanFailureMessageKey", () => {
  it("maps the known API sentences", () => {
    expect(chemistryScanFailureMessageKey("Not available")).toBe("chat.chemistry_scan_unavailable");
    expect(chemistryScanFailureMessageKey("something else")).toBeNull();
  });
});
