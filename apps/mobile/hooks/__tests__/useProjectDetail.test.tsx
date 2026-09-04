import React from "react";
import { Text } from "react-native";
import { act, render, waitFor } from "@testing-library/react-native";

import { useProjectDetail } from "@/hooks/useProjectDetail";

let mockFocusApplied = false;
jest.mock("expo-router", () => ({
  useFocusEffect: (callback: () => void) => {
    if (!mockFocusApplied) {
      mockFocusApplied = true;
      callback();
    }
  },
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuthToken: () => "token",
}));
const mockRefreshHome = jest.fn();
jest.mock("@/contexts/HomeContext", () => ({
  useHome: () => ({ refresh: mockRefreshHome }),
}));
jest.mock("@/lib/cache/projectDetailCache", () => ({
  fetchProjectDetail: jest.fn(),
  getCachedProjectDetail: jest.fn(),
}));

import {
  fetchProjectDetail,
  getCachedProjectDetail,
} from "@/lib/cache/projectDetailCache";

let current: ReturnType<typeof useProjectDetail>;

function Probe() {
  const result = useProjectDetail("p1");
  React.useLayoutEffect(() => {
    current = result;
  }, [result]);
  return <Text>{result.project?.title ?? "empty"}</Text>;
}

describe("useProjectDetail", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFocusApplied = false;
    (getCachedProjectDetail as jest.Mock).mockReturnValue({ id: "p1", title: "Cached" });
    (fetchProjectDetail as jest.Mock).mockResolvedValue({ id: "p1", title: "Fresh" });
  });

  it("paints cache, refreshes stale detail, and refreshes home silently", async () => {
    await act(async () => {
      render(<Probe />);
    });

    await waitFor(() => expect(current.project?.title).toBe("Fresh"));
    expect(fetchProjectDetail).toHaveBeenCalledWith("token", "p1", { force: true });
    expect(mockRefreshHome).toHaveBeenCalledWith({ silent: true });
  });
});
