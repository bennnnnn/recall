import { isNetworkOffline } from "@/lib/networkStatus";

describe("networkStatus", () => {
  it("is offline when not connected", () => {
    expect(isNetworkOffline({ isConnected: false, isInternetReachable: false } as never)).toBe(
      true,
    );
  });

  it("is offline when connected but internet is unreachable", () => {
    expect(isNetworkOffline({ isConnected: true, isInternetReachable: false } as never)).toBe(
      true,
    );
  });

  it("is online when connected and reachability is unknown", () => {
    expect(isNetworkOffline({ isConnected: true, isInternetReachable: null } as never)).toBe(
      false,
    );
  });

  it("is online when connected and internet is reachable", () => {
    expect(isNetworkOffline({ isConnected: true, isInternetReachable: true } as never)).toBe(
      false,
    );
  });
});
