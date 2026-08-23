import React from "react";
import { Text } from "react-native";
import { act, render, waitFor } from "@testing-library/react-native";

import { useGalleryData } from "@/hooks/useGalleryData";
import type { AttachmentListItem } from "@/lib/api";

jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "tok" }),
}));

jest.mock("expo-router", () => {
  const { useEffect } = require("react") as typeof import("react");
  return {
    useFocusEffect: (callback: () => void) => {
      useEffect(callback, [callback]);
    },
  };
});

jest.mock("@/lib/api", () => ({
  api: {
    listAttachments: jest.fn(),
  },
}));

import { api } from "@/lib/api";

function item(id: string): AttachmentListItem {
  return {
    id,
    content_type: "image/png",
    size_bytes: 12,
    download_url: `/attachments/${id}/file`,
    source: "upload",
    created_at: "2026-01-01T00:00:00.000Z",
  };
}

let latest: ReturnType<typeof useGalleryData> | null = null;

function Probe() {
  latest = useGalleryData("all", "");
  return <Text>{latest.items.map((row) => row.id).join(",")}</Text>;
}

describe("useGalleryData", () => {
  beforeEach(() => {
    latest = null;
    jest.clearAllMocks();
  });

  it("keeps the grid when a later page fails", async () => {
    const list = api.listAttachments as jest.Mock;
    list
      .mockResolvedValueOnce({ items: [item("a"), item("b")], has_more: true })
      .mockRejectedValueOnce(new Error("network"));

    await act(async () => {
      render(<Probe />);
    });
    await waitFor(() => {
      expect(latest?.items.map((row) => row.id)).toEqual(["a", "b"]);
    });

    await act(async () => {
      latest?.loadMore();
    });
    await waitFor(() => {
      expect(list).toHaveBeenCalledTimes(2);
    });
    expect(latest?.items.map((row) => row.id)).toEqual(["a", "b"]);
    expect(latest?.error).toBe(false);
  });

  it("appends the next page after loadMore", async () => {
    const list = api.listAttachments as jest.Mock;
    list
      .mockResolvedValueOnce({ items: [item("a")], has_more: true })
      .mockResolvedValueOnce({ items: [item("b")], has_more: false });

    await act(async () => {
      render(<Probe />);
    });
    await waitFor(() => {
      expect(latest?.items.map((row) => row.id)).toEqual(["a"]);
    });

    await act(async () => {
      latest?.loadMore();
    });
    await waitFor(() => {
      expect(latest?.items.map((row) => row.id)).toEqual(["a", "b"]);
    });
  });
});
