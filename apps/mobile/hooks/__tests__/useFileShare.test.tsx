/**
 * A Share button's spinner follows the share guard: when the watchdog lets go of a share that
 * never ends (iOS presenting no sheet), the button stops spinning too.
 */
import { act, renderHook } from "@testing-library/react-native";

import { useFileShare } from "@/hooks/useFileShare";
import { resetShareGuard } from "@/lib/share/file";

jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/lib/reportRecoverableError", () => ({ reportRecoverableWarning: jest.fn() }));

afterEach(() => {
  resetShareGuard();
  jest.useRealTimers();
});

it("stops spinning when the watchdog lets go of a share that never ends", async () => {
  jest.useFakeTimers();
  const { result } = await renderHook(() => useFileShare());
  let pending: Promise<void> | undefined;
  await act(async () => {
    pending = result.current.share(() => new Promise<void>(() => {}));
  });
  expect(result.current.sharing).toBe(true);
  await act(async () => {
    jest.advanceTimersByTime(180_000);
    await pending;
  });
  expect(result.current.sharing).toBe(false);
});

it("keeps the running share's spinner when a second press is refused", async () => {
  const { result } = await renderHook(() => useFileShare());
  let finish: () => void = () => {};
  let first: Promise<void> | undefined;
  await act(async () => {
    first = result.current.share(() => new Promise<void>((resolve) => { finish = resolve; }));
  });
  await act(async () => {
    await result.current.share(async () => {});
  });
  expect(result.current.sharing).toBe(true);
  await act(async () => {
    finish();
    await first;
  });
  expect(result.current.sharing).toBe(false);
});

it("stops spinning when the share ends", async () => {
  const { result } = await renderHook(() => useFileShare());
  await act(async () => {
    await result.current.share(async () => {});
  });
  expect(result.current.sharing).toBe(false);
});
