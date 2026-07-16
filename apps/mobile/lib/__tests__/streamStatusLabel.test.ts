import type { TFunction } from "i18next";

import {
  clipStreamStatusDetail,
  initialStreamStatusTick,
  pickRotatingStreamLabel,
  shouldShowWaitingIndicator,
  streamStatusLabels,
} from "@/lib/streamStatusLabel";

const t = ((key: string, options?: { detail?: string }) => {
  const map: Record<string, string> = {
    "chat.status.searching": "Searching the web…",
    "chat.status.searching_1": "Checking sources…",
    "chat.status.searching_detail": "Searching — “{{detail}}”",
    "chat.status.unknown": "missing",
  };
  const raw = map[key];
  if (raw === undefined) return key;
  return options?.detail !== undefined
    ? raw.replace("{{detail}}", options.detail)
    : raw;
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

  it("leads with the detail label when detail is provided", () => {
    expect(streamStatusLabels(t, "searching", "weather in berlin")).toEqual([
      "Searching — “weather in berlin”",
      "Searching the web…",
      "Checking sources…",
    ]);
  });

  it("ignores detail when the phase has no _detail template", () => {
    expect(streamStatusLabels(t, "not_a_real_phase", "x")).toEqual([]);
  });

  it("rotates through labels", () => {
    const labels = ["A", "B", "C"];
    expect(pickRotatingStreamLabel(labels, 0)).toBe("A");
    expect(pickRotatingStreamLabel(labels, 1)).toBe("B");
    expect(pickRotatingStreamLabel(labels, 3)).toBe("A");
  });
});

describe("shouldShowWaitingIndicator", () => {
  it("shows while streaming with no content and no reasoning", () => {
    expect(
      shouldShowWaitingIndicator({ isStreaming: true, hasContent: false, showReasoning: false }),
    ).toBe(true);
  });

  it("BUG FIX regression: hides once reasoning is already showing, so the generic status label doesn't duplicate the live reasoning block", () => {
    expect(
      shouldShowWaitingIndicator({ isStreaming: true, hasContent: false, showReasoning: true }),
    ).toBe(false);
  });

  it("hides once content has started arriving", () => {
    expect(
      shouldShowWaitingIndicator({ isStreaming: true, hasContent: true, showReasoning: false }),
    ).toBe(false);
  });

  it("hides when not streaming", () => {
    expect(
      shouldShowWaitingIndicator({ isStreaming: false, hasContent: false, showReasoning: false }),
    ).toBe(false);
  });
});

describe("clipStreamStatusDetail", () => {
  it("flattens whitespace and passes short details through", () => {
    expect(clipStreamStatusDetail("  weather \n in  berlin ")).toBe(
      "weather in berlin",
    );
  });

  it("truncates long details with an ellipsis", () => {
    const long = "a".repeat(120);
    const clipped = clipStreamStatusDetail(long);
    expect(clipped.length).toBeLessThanOrEqual(45);
    expect(clipped.endsWith("…")).toBe(true);
  });
});

describe("initialStreamStatusTick", () => {
  it("always starts at the detail label when present", () => {
    expect(initialStreamStatusTick(4, true, () => 0.9)).toBe(0);
  });

  it("starts at zero for single-label phases", () => {
    expect(initialStreamStatusTick(1, false, () => 0.9)).toBe(0);
  });

  it("randomizes the opening variant otherwise", () => {
    expect(initialStreamStatusTick(4, false, () => 0)).toBe(0);
    expect(initialStreamStatusTick(4, false, () => 0.5)).toBe(2);
    expect(initialStreamStatusTick(4, false, () => 0.99)).toBe(3);
  });
});
