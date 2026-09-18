import {
  hasAutomationCreatedFence,
  parseAutomationCreated,
  stripAutomationCreatedBlock,
} from "@/lib/parseAutomationCreated";

const AUTOMATION_ID = "11111111-1111-4111-8111-111111111111";
const VALID_FENCE = `\`\`\`automation_created\n{"id":"${AUTOMATION_ID}","prompt":"Find L3 backend jobs","frequency":"daily","next_run_at":"2026-09-19T08:00:00-04:00"}\n\`\`\``;

describe("parseAutomationCreated", () => {
  it("reads a valid fence", () => {
    expect(parseAutomationCreated(`Done — every day at 8am.\n\n${VALID_FENCE}`)).toEqual({
      id: AUTOMATION_ID,
      prompt: "Find L3 backend jobs",
      frequency: "daily",
      nextRunAt: "2026-09-19T08:00:00-04:00",
    });
  });

  it("rejects an unknown frequency instead of inventing one", () => {
    expect(
      parseAutomationCreated(
        `\`\`\`automation_created\n{"id":"${AUTOMATION_ID}","prompt":"x","frequency":"hourly","next_run_at":"2026-09-19T08:00:00-04:00"}\n\`\`\``,
      ),
    ).toBeNull();
  });

  it("rejects a missing field", () => {
    expect(
      parseAutomationCreated(`\`\`\`automation_created\n{"id":"${AUTOMATION_ID}","prompt":"x"}\n\`\`\``),
    ).toBeNull();
  });

  it("rejects invalid JSON", () => {
    expect(parseAutomationCreated("```automation_created\nnot json\n```")).toBeNull();
  });

  it("returns null when there is no fence", () => {
    expect(parseAutomationCreated("Sure — what should the task do?")).toBeNull();
  });
});

describe("hasAutomationCreatedFence", () => {
  it("detects a closed fence", () => {
    expect(hasAutomationCreatedFence(VALID_FENCE)).toBe(true);
  });

  it("detects an open streaming fence", () => {
    expect(hasAutomationCreatedFence('```automation_created\n{"id":"x"')).toBe(true);
  });

  it("is false with no fence", () => {
    expect(hasAutomationCreatedFence("plain text")).toBe(false);
  });
});

describe("stripAutomationCreatedBlock", () => {
  it("strips the fence from assistant prose", () => {
    expect(stripAutomationCreatedBlock(`Done — every day at 8am.\n\n${VALID_FENCE}`)).toBe(
      "Done — every day at 8am.",
    );
  });
});
