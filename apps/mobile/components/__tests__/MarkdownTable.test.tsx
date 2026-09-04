import { tableColumnWidth, tableShouldFreezeFirstColumn, resolveFrozenRowHeight } from "@/components/MarkdownTable";

describe("tableColumnWidth", () => {
  it("makes a 3-column comparison wider than the bubble so it can pan", () => {
    const viewport = 358;
    const width = tableColumnWidth(viewport, 3);
    expect(width * 3).toBeGreaterThan(viewport);
  });

  it("keeps 4+ columns at least the min readable width", () => {
    const viewport = 358;
    const width = tableColumnWidth(viewport, 4);
    expect(width).toBeGreaterThanOrEqual(168);
    expect(width * 4).toBeGreaterThan(viewport);
  });
});

describe("tableShouldFreezeFirstColumn", () => {
  it("freezes when 3+ columns overflow the viewport", () => {
    const viewport = 358;
    const width = tableColumnWidth(viewport, 3);
    expect(tableShouldFreezeFirstColumn(3, viewport, width)).toBe(true);
  });

  it("does not freeze a 2-column table", () => {
    const viewport = 358;
    const width = tableColumnWidth(viewport, 2);
    expect(tableShouldFreezeFirstColumn(2, viewport, width)).toBe(false);
  });
});

describe("resolveFrozenRowHeight", () => {
  it("uses the taller of the frozen label and the value row", () => {
    expect(resolveFrozenRowHeight(80, 40)).toBe(80);
    expect(resolveFrozenRowHeight(40, 80)).toBe(80);
    expect(resolveFrozenRowHeight(50, 50)).toBe(50);
    expect(resolveFrozenRowHeight(undefined, 40)).toBe(40);
  });
});
