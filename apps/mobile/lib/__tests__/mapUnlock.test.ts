import { syncMapUnlocks, acknowledgeMapUnlocks, resetMapUnlockState } from "@/lib/projects/mapUnlock";

describe("syncMapUnlocks", () => {
  beforeEach(() => {
    resetMapUnlockState();
  });

  it("does not celebrate groups that were already done on first look", () => {
    expect(syncMapUnlocks("p", ["Hello"])).toEqual([]);
    expect(syncMapUnlocks("p", ["Hello"])).toEqual([]);
  });

  it("returns a group that became done after the map was seeded", () => {
    expect(syncMapUnlocks("p", ["Hello"])).toEqual([]);
    expect(syncMapUnlocks("p", ["Hello", "Morning"])).toEqual(["Morning"]);
    acknowledgeMapUnlocks("p", ["Morning"]);
    expect(syncMapUnlocks("p", ["Hello", "Morning"])).toEqual([]);
  });
});
