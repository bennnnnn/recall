import React from "react";
import { Text } from "react-native";
import { act, render, waitFor } from "@testing-library/react-native";

import { useAttachmentIndexed } from "@/hooks/useAttachmentIndexed";

jest.mock("@/contexts/AuthContext", () => ({
  useAuthToken: () => "token",
}));

const mockGetAttachmentUrl = jest.fn();

jest.mock("@/lib/api", () => ({
  api: {
    getAttachmentUrl: (...args: unknown[]) => mockGetAttachmentUrl(...args),
  },
}));

let indexed: boolean;

function Probe({ attachmentId }: { attachmentId?: string }) {
  const result = useAttachmentIndexed(attachmentId);
  React.useLayoutEffect(() => {
    indexed = result;
  }, [result]);
  return <Text>{result ? "ready" : "indexing"}</Text>;
}

describe("useAttachmentIndexed", () => {
  beforeEach(() => {
    mockGetAttachmentUrl.mockReset();
  });

  it("is indexed when there is no attachment id", async () => {
    await act(async () => {
      render(<Probe />);
    });
    expect(indexed).toBe(true);
    expect(mockGetAttachmentUrl).not.toHaveBeenCalled();
  });

  it("stays unindexed while the url payload says indexed false", async () => {
    mockGetAttachmentUrl.mockResolvedValue({ indexed: false });
    await act(async () => {
      render(<Probe attachmentId="att-1" />);
    });
    await waitFor(() => expect(mockGetAttachmentUrl).toHaveBeenCalled());
    expect(indexed).toBe(false);
  });

  it("becomes indexed when the url payload says indexed true", async () => {
    mockGetAttachmentUrl.mockResolvedValue({ indexed: true });
    await act(async () => {
      render(<Probe attachmentId="att-1" />);
    });
    await waitFor(() => expect(indexed).toBe(true));
  });
});
