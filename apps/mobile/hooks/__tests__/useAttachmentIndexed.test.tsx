import React from "react";
import { Text } from "react-native";
import { act, render, waitFor } from "@testing-library/react-native";

import {
  INDEX_POLL_MAX_MS,
  useAttachmentIndexed,
} from "@/hooks/useAttachmentIndexed";

jest.mock("@/contexts/AuthContext", () => ({
  useAuthToken: () => "token",
}));

const mockGetAttachmentUrl = jest.fn();

jest.mock("@/lib/api", () => ({
  api: {
    getAttachmentUrl: (...args: unknown[]) => mockGetAttachmentUrl(...args),
  },
}));

let indexed = false;
let failed = false;

function Probe({ attachmentId }: { attachmentId?: string }) {
  const result = useAttachmentIndexed(attachmentId);
  React.useLayoutEffect(() => {
    indexed = result.indexed;
    failed = result.failed;
  }, [result]);
  return <Text>{result.failed ? "failed" : result.indexed ? "ready" : "indexing"}</Text>;
}

describe("useAttachmentIndexed", () => {
  beforeEach(() => {
    mockGetAttachmentUrl.mockReset();
    indexed = false;
    failed = false;
  });

  it("is indexed when there is no attachment id", async () => {
    await act(async () => {
      render(<Probe />);
    });
    expect(indexed).toBe(true);
    expect(failed).toBe(false);
    expect(mockGetAttachmentUrl).not.toHaveBeenCalled();
  });

  it("stays unindexed while the url payload says indexed false", async () => {
    mockGetAttachmentUrl.mockResolvedValue({ indexed: false });
    await act(async () => {
      render(<Probe attachmentId="att-1" />);
    });
    await waitFor(() => expect(mockGetAttachmentUrl).toHaveBeenCalled());
    expect(indexed).toBe(false);
    expect(failed).toBe(false);
  });

  it("becomes indexed when the url payload says indexed true", async () => {
    mockGetAttachmentUrl.mockResolvedValue({ indexed: true });
    await act(async () => {
      render(<Probe attachmentId="att-1" />);
    });
    await waitFor(() => expect(indexed).toBe(true));
    expect(failed).toBe(false);
  });

  it("keeps indexing through the job claim TTL, then marks failed", async () => {
    jest.useFakeTimers();
    mockGetAttachmentUrl.mockResolvedValue({ indexed: false });
    try {
      await act(async () => {
        render(<Probe attachmentId="att-1" />);
      });
      await waitFor(() => expect(mockGetAttachmentUrl).toHaveBeenCalled());
      await act(async () => {
        jest.advanceTimersByTime(60_000);
      });
      expect(failed).toBe(false);
      await act(async () => {
        jest.advanceTimersByTime(INDEX_POLL_MAX_MS);
      });
      expect(indexed).toBe(false);
      expect(failed).toBe(true);
    } finally {
      jest.useRealTimers();
    }
  });
});

it("does not report the next attachment ready while its status request is pending", async () => {
  mockGetAttachmentUrl.mockResolvedValueOnce({ indexed: true });
  const view = await render(<Probe attachmentId="ready" />);
  expect(indexed).toBe(true);
  mockGetAttachmentUrl.mockReturnValueOnce(new Promise(() => {}));
  await view.rerender(<Probe attachmentId="pending" />);
  expect(indexed).toBe(false);
  expect(failed).toBe(false);
});
