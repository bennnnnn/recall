export type ChatTtftBucket =
  | "lt500"
  | "500_999"
  | "1000_1999"
  | "2000_3999"
  | "4000_5999"
  | "6000_plus";

/** Bucket tap -> first-token latency without storing arbitrary timing values. */
export function chatTtftBucket(elapsedMs: number): ChatTtftBucket {
  const ms = Number.isFinite(elapsedMs) ? Math.max(0, elapsedMs) : 0;
  if (ms < 500) return "lt500";
  if (ms < 1_000) return "500_999";
  if (ms < 2_000) return "1000_1999";
  if (ms < 4_000) return "2000_3999";
  if (ms < 6_000) return "4000_5999";
  return "6000_plus";
}
