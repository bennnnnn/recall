import { act, renderHook } from "@testing-library/react-native";

import { useDataControls } from "@/features/account/hooks/useDataControls";

const mockExportText = jest.fn();
const mockShare = jest.fn();

jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "tok", signOut: jest.fn(), setIgnoreUnauthorized: jest.fn() }),
}));
jest.mock("@/lib/api", () => ({
  api: {
    exportDataText: (...args: unknown[]) => mockExportText(...args),
    deleteAccount: jest.fn(),
  },
}));
jest.mock("@/lib/exportData", () => ({
  formatExportJsonForShare: (raw: string) => raw,
  shareAccountExport: (...args: unknown[]) => mockShare(...args),
}));
jest.mock("@/lib/accountDelete", () => ({ isAccountDeleteComplete: () => false }));

beforeEach(() => jest.clearAllMocks());

it("exports and shares the file", async () => {
  mockExportText.mockResolvedValue("{}");
  const { result } = await renderHook(() => useDataControls());
  let done: boolean | undefined;
  await act(async () => {
    done = await result.current.exportData();
  });
  expect(done).toBe(true);
  expect(mockShare).toHaveBeenCalledWith("{}");
  expect(result.current.progress).toBe("idle");
});

it("cancelling stops the request and shares nothing", async () => {
  mockExportText.mockImplementation(
    (_token: string, signal: AbortSignal) =>
      new Promise((_resolve, reject) => {
        signal.addEventListener("abort", () => reject(new Error("Aborted")));
      }),
  );
  const { result } = await renderHook(() => useDataControls());
  let pending: Promise<boolean> | undefined;
  await act(async () => {
    pending = result.current.exportData();
  });
  expect(result.current.progress).toBe("exporting");
  await act(async () => {
    result.current.cancelExport();
  });
  await expect(pending).resolves.toBe(false);
  expect(mockShare).not.toHaveBeenCalled();
  expect(result.current.progress).toBe("idle");
});
