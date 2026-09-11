import { chatTtftBucket } from "@/lib/chatLatency";

describe("chatTtftBucket", () => {
  it.each([
    [0, "lt500"],
    [499, "lt500"],
    [500, "500_999"],
    [999, "500_999"],
    [1_000, "1000_1999"],
    [1_999, "1000_1999"],
    [2_000, "2000_3999"],
    [3_999, "2000_3999"],
    [4_000, "4000_5999"],
    [5_999, "4000_5999"],
    [6_000, "6000_plus"],
  ])("buckets %sms as %s", (elapsedMs, expected) => {
    expect(chatTtftBucket(elapsedMs as number)).toBe(expected);
  });
});
