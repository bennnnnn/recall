import React from "react";
import { Text } from "react-native";
import { act, render, waitFor } from "@testing-library/react-native";

import { useAttachmentIndexed } from "@/features/attachments/hooks/useAttachmentIndexed";
import {
  INDEX_POLL_MAX_MS,
  resetAttachmentIndexStatus,
} from "@/features/attachments/model/attachmentIndexStatus";

jest.mock("@/contexts/AuthContext", () => ({
  useAuthToken: () => "token",
}));

const mockGetAttachmentUrl = jest.fn();

jest.mock("@/lib/api", () => ({
  api: {
    getAttachmentUrl: (...args: unknown[]) => mockGetAttachmentUrl(...args),
  },
}));

jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 0 }));

type NetListener = (state: { isConnected: boolean | null; isInternetReachable: boolean | null }) => void;
const mockNetListeners = new Set<NetListener>();
jest.mock("@react-native-community/netinfo", () => ({
  __esModule: true,
  default: {
    addEventListener: (listener: NetListener) => {
      mockNetListeners.add(listener);
      return () => mockNetListeners.delete(listener);
    },
  },
}));

function setConnected(isConnected: boolean) {
  mockNetListeners.forEach((listener) => listener({ isConnected, isInternetReachable: isConnected }));
}

beforeEach(() => {
  mockGetAttachmentUrl.mockReset();
  resetAttachmentIndexStatus();
  mockNetListeners.clear();
});

let indexed = false;
let failed = false;
let fileName: string | null | undefined;

function Probe({ attachmentId }: { attachmentId?: string }) {
  const result = useAttachmentIndexed(attachmentId);
  React.useLayoutEffect(() => {
    indexed = result.indexed;
    failed = result.failed;
    fileName = result.fileName;
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

  it("asks once about an old attachment that will never be indexed", async () => {
    jest.useFakeTimers();
    // A file with no extractable text stays `indexed: false` forever. Old
    // chats with one polled every 2 seconds for 6 minutes, again on every
    // visit and every time the list reused the row.
    mockGetAttachmentUrl.mockResolvedValue({
      indexed: false,
      created_at: new Date(Date.now() - 60 * 60_000).toISOString(),
    });
    try {
      await act(async () => {
        render(<Probe attachmentId="old-scan" />);
      });
      await waitFor(() => expect(failed).toBe(true));
      await act(async () => {
        jest.advanceTimersByTime(60_000);
      });
      expect(mockGetAttachmentUrl).toHaveBeenCalledTimes(1);
      expect(indexed).toBe(false);
    } finally {
      jest.useRealTimers();
    }
  });

  it("keeps polling a just-uploaded attachment", async () => {
    jest.useFakeTimers();
    mockGetAttachmentUrl.mockResolvedValue({
      indexed: false,
      created_at: new Date().toISOString(),
    });
    try {
      await act(async () => {
        render(<Probe attachmentId="fresh" />);
      });
      await act(async () => {
        jest.advanceTimersByTime(10_000);
      });
      expect(mockGetAttachmentUrl.mock.calls.length).toBeGreaterThan(1);
      expect(failed).toBe(false);
    } finally {
      jest.useRealTimers();
    }
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

it("shares one poller between rows showing the same attachment and remembers a settled answer", async () => {
  mockGetAttachmentUrl.mockResolvedValue({ indexed: true });
  const view = await render(
    <>
      <Probe attachmentId="shared" />
      <Probe attachmentId="shared" />
    </>,
  );
  await waitFor(() => expect(indexed).toBe(true));
  expect(mockGetAttachmentUrl).toHaveBeenCalledTimes(1);
  // A FlashList remount reads the remembered answer instead of asking again.
  await view.unmount();
  await render(<Probe attachmentId="shared" />);
  expect(indexed).toBe(true);
  expect(mockGetAttachmentUrl).toHaveBeenCalledTimes(1);
});

it("names the file from the server, before it is indexed and after", async () => {
  // A reopened message links only the file; without this its card said "document.pdf".
  jest.useFakeTimers();
  fileName = undefined;
  mockGetAttachmentUrl.mockResolvedValue({
    indexed: false,
    created_at: new Date().toISOString(),
    original_filename: "lease-notes.pdf",
  });
  try {
    await act(async () => {
      render(<Probe attachmentId="named" />);
    });
    expect(fileName).toBe("lease-notes.pdf");
    expect(indexed).toBe(false);
    mockGetAttachmentUrl.mockResolvedValue({ indexed: true });
    await act(async () => {
      jest.advanceTimersByTime(60_000);
    });
    expect(indexed).toBe(true);
    expect(fileName).toBe("lease-notes.pdf");
  } finally {
    jest.useRealTimers();
  }
});

it("backs off between polls", async () => {
  jest.useFakeTimers();
  mockGetAttachmentUrl.mockResolvedValue({ indexed: false, created_at: new Date().toISOString() });
  try {
    await act(async () => {
      render(<Probe attachmentId="slow" />);
    });
    await act(async () => {
      jest.advanceTimersByTime(60_000);
    });
    // A fixed 2 s poll would ask 31 times in a minute.
    expect(mockGetAttachmentUrl.mock.calls.length).toBeLessThan(12);
  } finally {
    jest.useRealTimers();
  }
});

it("pauses while offline and resumes on reconnect", async () => {
  jest.useFakeTimers();
  mockGetAttachmentUrl.mockResolvedValue({ indexed: false, created_at: new Date().toISOString() });
  try {
    await act(async () => {
      render(<Probe attachmentId="offline" />);
    });
    expect(mockGetAttachmentUrl).toHaveBeenCalledTimes(1);
    await act(async () => {
      setConnected(false);
      jest.advanceTimersByTime(60_000);
    });
    const whileOffline = mockGetAttachmentUrl.mock.calls.length;
    await act(async () => {
      jest.advanceTimersByTime(60_000);
    });
    expect(mockGetAttachmentUrl).toHaveBeenCalledTimes(whileOffline);
    mockGetAttachmentUrl.mockResolvedValue({ indexed: true });
    await act(async () => {
      setConnected(true);
    });
    expect(mockGetAttachmentUrl).toHaveBeenCalledTimes(whileOffline + 1);
    expect(indexed).toBe(true);
  } finally {
    jest.useRealTimers();
  }
});

it("stops polling when no row shows the attachment", async () => {
  jest.useFakeTimers();
  mockGetAttachmentUrl.mockResolvedValue({ indexed: false, created_at: new Date().toISOString() });
  try {
    const view = await render(<Probe attachmentId="gone" />);
    await view.unmount();
    await act(async () => {
      jest.advanceTimersByTime(60_000);
    });
    expect(mockGetAttachmentUrl).toHaveBeenCalledTimes(1);
  } finally {
    jest.useRealTimers();
  }
});
