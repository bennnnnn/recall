import { act, renderHook } from "@testing-library/react-native";

import { useUpgradeSheet } from "@/features/chat/hooks/useUpgradeSheet";

describe("useUpgradeSheet", () => {
  it("opens the plans with where they were opened from, and closes them keeping it", async () => {
    const { result } = await renderHook(() => useUpgradeSheet());
    expect(result.current).toMatchObject({ visible: false, source: "other" });

    await act(async () => result.current.open("voice"));
    expect(result.current).toMatchObject({ visible: true, source: "voice" });

    await act(async () => result.current.close());
    expect(result.current).toMatchObject({ visible: false, source: "voice" });
  });

  it("names an open with no source 'other'", async () => {
    const { result } = await renderHook(() => useUpgradeSheet());
    await act(async () => result.current.open("quota"));
    await act(async () => result.current.open());
    expect(result.current.source).toBe("other");
  });

  it("keeps open and close the same across renders, for the hooks that hold them", async () => {
    const { result, rerender } = await renderHook(() => useUpgradeSheet());
    const { open, close } = result.current;
    await act(async () => open("live_talk"));
    await rerender({});
    expect(result.current.open).toBe(open);
    expect(result.current.close).toBe(close);
  });
});
