import { EAGER_CONNECT_DEBOUNCE_MS, WS_CONNECT_TIMEOUT_MS } from "@/lib/chatWsConnect";

describe("chatWsConnect", () => {
  it("falls back to SSE before an 8s silent wait", () => {
    expect(WS_CONNECT_TIMEOUT_MS).toBe(1_500);
    expect(WS_CONNECT_TIMEOUT_MS).toBeLessThan(8_000);
    expect(EAGER_CONNECT_DEBOUNCE_MS).toBe(300);
  });
});
