import { act, renderHook } from "@testing-library/react-native";

import { useLibraryStorage } from "@/features/account/hooks/useLibraryStorage";

let mockAccount: string | null = "u1";
let mockToken = "tok-1";
let mockPlan = "free";
const mockGetStorage = jest.fn();

jest.mock("expo-router", () => ({
  useFocusEffect: (effect: () => void | (() => void)) =>
    (jest.requireActual("react") as typeof import("react")).useEffect(effect, [effect]),
}));
jest.mock("@/contexts/accountSession", () => {
  const getToken = () => mockToken;
  return { useAccountSession: () => ({ account: mockAccount, getToken }) };
});
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ user: { plan: mockPlan } }) }));
jest.mock("@/features/attachments/api", () => ({
  attachmentsApi: { getLibraryStorage: (token: string) => mockGetStorage(token) },
}));
jest.mock("@/hooks/useReconnectRefresh", () => ({ useReconnectRefresh: () => undefined }));
jest.mock("@/lib/sentry", () => ({ reportFailure: jest.fn() }));
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 1 }));

const MB = 1024 ** 2;

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

beforeEach(() => {
  mockAccount = "u1";
  mockToken = "tok-1";
  mockPlan = "free";
  mockGetStorage.mockReset();
});

it("shows what Library keeps of the plan's total", async () => {
  mockGetStorage.mockResolvedValue({ used_bytes: 120 * MB, limit_bytes: 400 * MB });
  const { result } = await renderHook(() => useLibraryStorage());
  await act(async () => {});
  expect(mockGetStorage).toHaveBeenCalledWith("tok-1");
  expect(result.current).toEqual({ usedBytes: 120 * MB, limitBytes: 400 * MB });
});

it("never shows a free plan's answer once the plan is Pro", async () => {
  const freeRead = deferred<{ used_bytes: number; limit_bytes: number }>();
  mockGetStorage.mockReturnValueOnce(freeRead.promise);
  const { result, rerender } = await renderHook(() => useLibraryStorage());
  // The plan changes while the free plan's read is still out; Pro's read stays out.
  mockPlan = "pro";
  mockGetStorage.mockReturnValueOnce(new Promise(() => {}));
  await rerender({});
  await act(async () => freeRead.resolve({ used_bytes: 120 * MB, limit_bytes: 400 * MB }));
  expect(result.current).toBeNull();
});

it("never shows another account's answer", async () => {
  const firstRead = deferred<{ used_bytes: number; limit_bytes: number }>();
  mockGetStorage.mockReturnValueOnce(firstRead.promise);
  const { result, rerender } = await renderHook(() => useLibraryStorage());
  mockAccount = "u2";
  mockGetStorage.mockReturnValueOnce(new Promise(() => {}));
  await rerender({});
  await act(async () => firstRead.resolve({ used_bytes: 120 * MB, limit_bytes: 400 * MB }));
  expect(result.current).toBeNull();
});

it("reads nothing again when only the token rotates", async () => {
  mockGetStorage.mockResolvedValue({ used_bytes: 0, limit_bytes: 400 * MB });
  const { rerender } = await renderHook(() => useLibraryStorage());
  await act(async () => {});
  mockToken = "tok-2";
  await rerender({});
  await act(async () => {});
  expect(mockGetStorage).toHaveBeenCalledTimes(1);
});
