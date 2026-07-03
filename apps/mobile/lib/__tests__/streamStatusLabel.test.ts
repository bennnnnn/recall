import type { TFunction } from "i18next";

import { pickRotatingStreamLabel, streamStatusLabels } from "@/lib/streamStatusLabel";

const t = ((key: string) => {
  const map: Record<string, string> = {
    "chat.status.searching": "Searching the web…",
    "chat.status.searching_1": "Checking sources…",
    "chat.status.unknown": "missing",
  };
  return map[key] ?? key;
}) as TFunction;

describe("streamStatusLabels", () => {
  it("collects base and numbered variants", () => {
    expect(streamStatusLabels(t, "searching")).toEqual([
      "Searching the web…",
      "Checking sources…",
    ]);
  });

  it("returns empty when phase is unknown", () => {
    expect(streamStatusLabels(t, "not_a_real_phase")).toEqual([]);
  });

  it("rotates through labels", () => {
    const labels = ["A", "B", "C"];
    expect(pickRotatingStreamLabel(labels, 0)).toBe("A");
    expect(pickRotatingStreamLabel(labels, 1)).toBe("B");
    expect(pickRotatingStreamLabel(labels, 3)).toBe("A");
  });
});
