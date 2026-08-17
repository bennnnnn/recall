import { isAccountDeleteComplete } from "@/lib/accountDelete";

describe("isAccountDeleteComplete", () => {
  it("treats 401/404 as the wipe already started", () => {
    expect(isAccountDeleteComplete({ status: 401 })).toBe(true);
    expect(isAccountDeleteComplete({ status: 404 })).toBe(true);
  });

  it("does not treat a failed wipe as done", () => {
    expect(isAccountDeleteComplete({ status: 500 })).toBe(false);
    expect(isAccountDeleteComplete(new Error("network"))).toBe(false);
  });
});
