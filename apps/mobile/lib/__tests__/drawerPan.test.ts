import { DRAWER_EDGE_WIDTH, shouldClaimDrawerPan } from "@/lib/drawerPan";

const w = 320;

describe("shouldClaimDrawerPan", () => {
  it("opens from a rightward edge swipe when closed", () => {
    expect(
      shouldClaimDrawerPan({
        open: false,
        startX: 8,
        dx: 20,
        dy: 2,
        drawerWidth: w,
      }),
    ).toBe(true);
  });

  it("ignores a closed-drawer swipe that does not start on the edge", () => {
    expect(
      shouldClaimDrawerPan({
        open: false,
        startX: DRAWER_EDGE_WIDTH + 10,
        dx: 24,
        dy: 0,
        drawerWidth: w,
      }),
    ).toBe(false);
  });

  it("drags the open panel left or right", () => {
    expect(
      shouldClaimDrawerPan({
        open: true,
        startX: 80,
        dx: -24,
        dy: 4,
        drawerWidth: w,
      }),
    ).toBe(true);
    expect(
      shouldClaimDrawerPan({
        open: true,
        startX: 80,
        dx: 24,
        dy: 4,
        drawerWidth: w,
      }),
    ).toBe(true);
  });

  it("closes from a leftward scrim swipe when open", () => {
    expect(
      shouldClaimDrawerPan({
        open: true,
        startX: w + 10,
        dx: -20,
        dy: 0,
        drawerWidth: w,
      }),
    ).toBe(true);
  });

  it("lets the list scroll when the move is mostly vertical", () => {
    expect(
      shouldClaimDrawerPan({
        open: true,
        startX: 80,
        dx: 8,
        dy: 30,
        drawerWidth: w,
      }),
    ).toBe(false);
  });
});
