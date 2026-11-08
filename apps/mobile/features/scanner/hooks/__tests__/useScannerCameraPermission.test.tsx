import { act, renderHook } from "@testing-library/react-native";
import { AppState, type AppStateStatus } from "react-native";

import { useScannerCameraPermission } from "@/features/scanner/hooks/useScannerCameraPermission";

/** What the phone's settings say now; a test flips it as a student would in Settings. */
const mockCamera = { granted: false };
const mockReads = jest.fn();

// The permission hook as expo builds it: it holds what it last read, and reads when asked.
jest.mock("expo-image-picker", () => {
  const { useCallback, useState } = jest.requireActual<typeof import("react")>("react");
  return {
    useCameraPermissions: () => {
      const [status, setStatus] = useState<{ granted: boolean; canAskAgain: boolean } | null>(null);
      const read = useCallback(async () => {
        mockReads();
        const next = { granted: mockCamera.granted, canAskAgain: false };
        setStatus(next);
        return next;
      }, []);
      return [status, jest.fn(), read];
    },
  };
});

/** The app goes to the phone's Settings and comes back. */
async function returnFromSettings() {
  const listener = jest.mocked(AppState.addEventListener).mock.calls.at(-1)?.[1] as
    | ((state: AppStateStatus) => void)
    | undefined;
  if (!listener) throw new Error("nothing listens for the app coming back");
  await act(async () => {
    listener("background");
    listener("active");
  });
}

beforeEach(() => {
  mockCamera.granted = false;
  mockReads.mockClear();
});

describe("useScannerCameraPermission", () => {
  it("sees a camera allowed in Settings when the app comes back to the open scanner", async () => {
    const { result } = await renderHook(() => useScannerCameraPermission(true));
    expect(result.current[0]?.granted).toBe(false);

    mockCamera.granted = true;
    await returnFromSettings();

    expect(result.current[0]?.granted).toBe(true);
  });

  it("reads again each time the scanner opens, and not while it is closed", async () => {
    const { result, rerender } = await renderHook(
      ({ open }: { open: boolean }) => useScannerCameraPermission(open),
      { initialProps: { open: true } },
    );
    expect(mockReads).toHaveBeenCalledTimes(1);

    await rerender({ open: false });
    mockCamera.granted = true;
    expect(mockReads).toHaveBeenCalledTimes(1);

    await rerender({ open: true });
    expect(mockReads).toHaveBeenCalledTimes(2);
    expect(result.current[0]?.granted).toBe(true);
  });
});
