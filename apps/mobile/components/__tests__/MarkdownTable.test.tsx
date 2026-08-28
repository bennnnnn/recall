import { tableColumnWidth } from "@/components/MarkdownTable";

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
