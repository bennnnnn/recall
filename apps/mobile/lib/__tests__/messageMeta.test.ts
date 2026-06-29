import {
  recalledMemoryCount,
  shouldShowRecalledChip,
} from "@/lib/messageMeta";

describe("messageMeta", () => {
  it("shows recalled chip only on last non-streaming assistant reply", () => {
    expect(
      shouldShowRecalledChip(
        { role: "assistant", recalled: 2 },
        { isStreaming: false, isLastAssistant: true },
      ),
    ).toBe(true);
    expect(
      shouldShowRecalledChip(
        { role: "assistant", recalled: 2 },
        { isStreaming: true, isLastAssistant: true },
      ),
    ).toBe(false);
    expect(
      shouldShowRecalledChip(
        { role: "assistant", recalled: 2 },
        { isStreaming: false, isLastAssistant: false },
      ),
    ).toBe(false);
    expect(
      shouldShowRecalledChip(
        { role: "user", recalled: 2 },
        { isStreaming: false, isLastAssistant: true },
      ),
    ).toBe(false);
  });

  it("recalledMemoryCount clamps missing values", () => {
    expect(recalledMemoryCount({ recalled: 3 })).toBe(3);
    expect(recalledMemoryCount({})).toBe(0);
  });
});
