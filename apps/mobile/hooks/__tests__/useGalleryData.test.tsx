import React from "react";
import { Text } from "react-native";
import { act, render, waitFor } from "@testing-library/react-native";

import { useGalleryData } from "@/hooks/useGalleryData";
import type { AttachmentListItem } from "@/lib/api";
import type { GalleryFilter } from "@/lib/gallery";

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
import { invalidateGalleryCache, setGalleryPage } from "@/lib/cache/galleryListCache";

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
let setProbeFilter: ((next: GalleryFilter) => void) | null = null;

function Probe({ filter = "all" }: { filter?: GalleryFilter }) {
  const result = useGalleryData(filter, "");
  React.useLayoutEffect(() => {
    latest = result;
  }, [result]);
  return <Text>{result.items.map((row) => row.id).join(",")}</Text>;
}

function FilterSwitchProbe() {
  const [filter, setFilter] = React.useState<GalleryFilter>("files");
  const result = useGalleryData(filter, "");
  React.useLayoutEffect(() => {
    setProbeFilter = setFilter;
    latest = result;
  }, [result]);
  return <Text>{result.items.map((row) => row.id).join(",")}</Text>;
}

describe("useGalleryData", () => {
  beforeEach(() => {
    latest = null;
    setProbeFilter = null;
    jest.clearAllMocks();
    invalidateGalleryCache();
    (api.listAttachments as jest.Mock).mockReset();
  });

  it("skips a second silent reset while the list is still fresh", async () => {
    const list = api.listAttachments as jest.Mock;
    list.mockResolvedValue({ items: [item("a")], has_more: false });

    await act(async () => {
      render(<Probe />);
    });
    await waitFor(() => {
      expect(latest?.items.map((row) => row.id)).toEqual(["a"]);
    });
    expect(list).toHaveBeenCalledTimes(1);

    await act(async () => {
      await latest?.retry();
    });
    expect(list).toHaveBeenCalledTimes(1);
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

  it("refetches when the visible filter changes even if another tab is fresh", async () => {
    const list = api.listAttachments as jest.Mock;
    list
      .mockResolvedValueOnce({ items: [item("pdf-1")], has_more: false })
      .mockResolvedValueOnce({ items: [item("img-1")], has_more: false });

    await act(async () => {
      render(<FilterSwitchProbe />);
    });
    await waitFor(() => {
      expect(latest?.items.map((row) => row.id)).toEqual(["pdf-1"]);
    });

    await act(async () => {
      setProbeFilter?.("all");
    });
    await waitFor(() => {
      expect(latest?.items.map((row) => row.id)).toEqual(["img-1"]);
    });
    expect(list).toHaveBeenCalledTimes(2);
  });

  it("hydrates from cache without refetching while fresh", async () => {
    const list = api.listAttachments as jest.Mock;
    setGalleryPage("all", "", { items: [item("cached")], hasMore: false });

    await act(async () => {
      render(<Probe />);
    });
    await waitFor(() => {
      expect(latest?.items.map((row) => row.id)).toEqual(["cached"]);
    });
    expect(list).not.toHaveBeenCalled();
  });

  it("restores a fresh tab snapshot without refetching", async () => {
    const list = api.listAttachments as jest.Mock;
    list
      .mockResolvedValueOnce({ items: [item("pdf-1")], has_more: false })
      .mockResolvedValueOnce({ items: [item("img-1")], has_more: false });

    await act(async () => {
      render(<FilterSwitchProbe />);
    });
    await waitFor(() => {
      expect(latest?.items.map((row) => row.id)).toEqual(["pdf-1"]);
    });

    await act(async () => {
      setProbeFilter?.("all");
    });
    await waitFor(() => {
      expect(latest?.items.map((row) => row.id)).toEqual(["img-1"]);
    });

    await act(async () => {
      setProbeFilter?.("files");
    });
    await waitFor(() => {
      expect(latest?.items.map((row) => row.id)).toEqual(["pdf-1"]);
    });
    expect(list).toHaveBeenCalledTimes(2);
  });

  it("drops a missing attachment from the grid", async () => {
    const list = api.listAttachments as jest.Mock;
    list.mockResolvedValue({ items: [item("a"), item("b")], has_more: false });

    await act(async () => {
      render(<Probe />);
    });
    await waitFor(() => {
      expect(latest?.items.map((row) => row.id)).toEqual(["a", "b"]);
    });

    await act(async () => {
      latest?.removeItem("a");
    });
    expect(latest?.items.map((row) => row.id)).toEqual(["b"]);
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
