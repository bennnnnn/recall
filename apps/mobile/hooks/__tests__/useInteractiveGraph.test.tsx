import { seedGraphSeries } from "@/hooks/useInteractiveGraph";

describe("seedGraphSeries", () => {
  it("locks the original function and seeds a second overlay", () => {
    const rows = seedGraphSeries(["x^2", "x^2/3"]);
    expect(rows).toHaveLength(2);
    expect(rows[0].locked).toBe(true);
    expect(rows[0].expr).toBe("x^2");
    expect(rows[1].locked).toBe(false);
    expect(rows[1].expr).toBe("x^2/3");
  });
});
