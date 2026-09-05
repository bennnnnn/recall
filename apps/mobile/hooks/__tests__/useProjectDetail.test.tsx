import React, { useLayoutEffect } from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";
import { useProjectDetail } from "@/hooks/useProjectDetail";
import { fetchProjectDetail, getCachedProjectDetail } from "@/lib/cache/projectDetailCache";
let mockSession = 1;
let mockToken = "token";
jest.mock("expo-router", () => ({
  useFocusEffect: (callback: () => void) =>
    jest.requireActual("react").useEffect(callback, [callback]),
}));
jest.mock("@/contexts/AuthContext", () => ({ useAuthToken: () => mockToken }));
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/lib/cache/projectDetailCache", () => ({
  fetchProjectDetail: jest.fn(),
  getCachedProjectDetail: jest.fn(),
  subscribeProjectDetailCache: () => () => {},
}));
let current: ReturnType<typeof useProjectDetail>;
function Probe({ id = "p1" }: { id?: string }) {
  const value = useProjectDetail(id);
  useLayoutEffect(() => {
    current = value;
  });
  return <Text>{value.project?.title ?? "empty"}</Text>;
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
beforeEach(() => {
  jest.clearAllMocks();
  mockSession += 1;
  mockToken = "token";
  (getCachedProjectDetail as jest.Mock).mockReturnValue(undefined);
});
it("preserves cached content and exposes failed refresh for retry", async () => {
  (getCachedProjectDetail as jest.Mock).mockReturnValue({ id: "p1", title: "Cached" });
  (fetchProjectDetail as jest.Mock)
    .mockResolvedValueOnce(null)
    .mockResolvedValueOnce({ id: "p1", title: "Fresh" });
  await render(<Probe />);
  expect(current.project?.title).toBe("Cached");
  expect(current.loadError).toBe(true);
  await act(() => current.load({ force: true }));
  expect(current.project?.title).toBe("Fresh");
  expect(current.loadError).toBe(false);
});
it("masks the prior project on account change and ignores its late result and callback", async () => {
  const old = deferred<unknown>();
  (fetchProjectDetail as jest.Mock)
    .mockReturnValueOnce(old.promise)
    .mockResolvedValueOnce({ id: "p1", title: "New account" });
  const screen = await render(<Probe />);
  const oldLoad = current.load;
  mockSession += 1;
  mockToken = "other";
  await screen.rerender(<Probe />);
  await act(async () => {
    old.resolve({ id: "p1", title: "Old account" });
  });
  expect(current.project?.title).toBe("New account");
  await act(() => oldLoad());
  expect(fetchProjectDetail).toHaveBeenCalledTimes(2);
});
it("token refresh keeps the current owner and uses the latest token for retry", async () => {
  (fetchProjectDetail as jest.Mock).mockResolvedValue({ id: "p1", title: "Class" });
  const screen = await render(<Probe />);
  const load = current.load;
  mockToken = "refreshed";
  await screen.rerender(<Probe />);
  expect(fetchProjectDetail).toHaveBeenCalledTimes(1);
  await act(() => load({ force: true }));
  expect(fetchProjectDetail).toHaveBeenLastCalledWith("refreshed", "p1", { force: true });
});
it("ignores a response after leaving the view", async () => {
  const old = deferred<unknown>();
  (fetchProjectDetail as jest.Mock).mockReturnValue(old.promise);
  const screen = await render(<Probe />);
  const load = current.load;
  await screen.unmount();
  await act(async () => {
    old.resolve({ title: "Late" });
    await load();
  });
  expect(fetchProjectDetail).toHaveBeenCalledTimes(1);
});
