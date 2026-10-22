import { useLayoutEffect } from "react";
import { act, render } from "@testing-library/react-native";

import { resetQuotaNudgeDismissal, useQuotaNudge } from "@/features/chat/hooks/useQuotaNudge";
import { api } from "@/lib/api";

jest.mock("@/lib/api", () => ({ api: { todayUsage: jest.fn() } }));

const nearlySpent = {
  date: "2026-10-21", input_tokens: 0, output_tokens: 0, daily_limit: 100_000, remaining: 10_000,
};

let nudge: ReturnType<typeof useQuotaNudge>;
let planKnown = false;
function Probe({ token, isPaid, refreshKey = 0 }: { token: string | null; isPaid: boolean; refreshKey?: number }) {
  const value = useQuotaNudge({ token, isPaid, planKnown, refreshKey });
  useLayoutEffect(() => { nudge = value; });
  return null;
}

beforeEach(() => {
  jest.clearAllMocks();
  resetQuotaNudgeDismissal();
  planKnown = false;
  jest.mocked(api.todayUsage).mockResolvedValue(nearlySpent);
});

it("waits for the server's plan before asking for today's usage", async () => {
  // The launch cache paints every plan as free; a paid account must not fetch.
  const ui = await render(<Probe token="tok" isPaid={false} />);
  await act(async () => {});
  expect(api.todayUsage).not.toHaveBeenCalled();

  planKnown = true;
  await ui.rerender(<Probe token="tok" isPaid />);
  await act(async () => {});
  expect(api.todayUsage).not.toHaveBeenCalled();
  expect(nudge.show).toBe(false);
});

it("nudges a free account near its daily limit once the plan is confirmed", async () => {
  const ui = await render(<Probe token="tok" isPaid={false} />);
  planKnown = true;
  await ui.rerender(<Probe token="tok" isPaid={false} />);
  await act(async () => {});
  expect(api.todayUsage).toHaveBeenCalledTimes(1);
  expect(api.todayUsage).toHaveBeenCalledWith("tok");
  expect(nudge.show).toBe(true);
  expect(nudge.usedPct).toBe(90);
});

it("does not fetch again when only the access token rotates", async () => {
  planKnown = true;
  const ui = await render(<Probe token="tok" isPaid={false} />);
  await act(async () => {});
  await ui.rerender(<Probe token="tok-refreshed" isPaid={false} />);
  await act(async () => {});
  expect(api.todayUsage).toHaveBeenCalledTimes(1);

  // A finished turn still refreshes, with the newest token.
  await ui.rerender(<Probe token="tok-refreshed" isPaid={false} refreshKey={1} />);
  await act(async () => {});
  expect(api.todayUsage).toHaveBeenCalledTimes(2);
  expect(api.todayUsage).toHaveBeenLastCalledWith("tok-refreshed");
});
