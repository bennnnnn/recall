const platform = { OS: "ios" };

jest.mock("react-native", () => ({
  Platform: platform,
  Share: { share: jest.fn(), sharedAction: "sharedAction", dismissedAction: "dismissedAction" },
}));

jest.mock("expo-print", () => ({ printToFileAsync: jest.fn() }));

import { Share } from "react-native";

import { describeLastRun, formatScheduleAt, shareAutomation } from "@/lib/automations/schedule";
import type { Automation } from "@/lib/api/types";

const t = ((key: string, opts?: Record<string, unknown>) =>
  opts?.date ? `${key}:${opts.date}` : key) as never;

const baseAutomation: Automation = {
  id: "auto-1",
  chat_id: "chat-1",
  prompt: "Find L3 backend jobs posted today",
  frequency: "daily",
  next_run_at: new Date(Date.now() + 86_400_000).toISOString(),
  status: "active",
  last_run_at: null,
  last_run_status: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

describe("formatScheduleAt", () => {
  it("returns an empty string for an unparsable date", () => {
    expect(formatScheduleAt("not-a-date")).toBe("");
  });

  it("labels today as just the time", () => {
    const now = new Date();
    expect(formatScheduleAt(now.toISOString())).not.toMatch(/Tomorrow|Yesterday/);
  });
});

describe("describeLastRun", () => {
  it("reports never-run when there is no last run", () => {
    expect(describeLastRun(baseAutomation, t)).toBe("automations.last_run_never");
  });

  it("reports ok status with a formatted date", () => {
    const automation: Automation = {
      ...baseAutomation,
      last_run_at: new Date().toISOString(),
      last_run_status: "ok",
    };
    expect(describeLastRun(automation, t)).toMatch(/^automations\.last_run_ok:/);
  });

  it("reports quota-skipped status", () => {
    const automation: Automation = {
      ...baseAutomation,
      last_run_at: new Date().toISOString(),
      last_run_status: "skipped_quota",
    };
    expect(describeLastRun(automation, t)).toMatch(/^automations\.last_run_skipped_quota:/);
  });

  it("reports error status", () => {
    const automation: Automation = {
      ...baseAutomation,
      last_run_at: new Date().toISOString(),
      last_run_status: "error",
    };
    expect(describeLastRun(automation, t)).toMatch(/^automations\.last_run_error:/);
  });
});

describe("shareAutomation", () => {
  beforeEach(() => {
    jest.mocked(Share.share).mockReset();
    jest.mocked(Share.share).mockResolvedValue({ action: Share.sharedAction });
  });

  it("shares the prompt and schedule as plain text", async () => {
    await shareAutomation(baseAutomation, t);
    expect(Share.share).toHaveBeenCalledTimes(1);
    const [payload] = jest.mocked(Share.share).mock.calls[0];
    expect(payload.message).toContain(baseAutomation.prompt);
    expect(payload.message).toContain("automations.frequency_daily");
    expect(payload.title).toBe(baseAutomation.prompt);
  });

  it("does not throw when the user dismisses the share sheet", async () => {
    jest.mocked(Share.share).mockRejectedValueOnce(new Error("User did not share"));
    await expect(shareAutomation(baseAutomation, t)).resolves.toBeUndefined();
  });
});
