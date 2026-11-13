import { numberLineMarkLabels } from "@/lib/math/numberLineMarks";

describe("the numbers a number line shows", () => {
  it("puts labels that would touch on two rows", () => {
    const toPx = (v: number) => 100 + v * 20;
    const labels = numberLineMarkLabels(
      [
        { x: 0.75, label: "3/4" },
        { x: 1.5, label: "1.5" },
        { x: -2.5, label: "−5/2" },
      ],
      toPx,
    );
    expect(labels.map((l) => [l.text, l.row])).toEqual([
      ["−5/2", 0],
      ["3/4", 0],
      ["1.5", 1],
    ]);
  });

  it("draws no label for a mark without one", () => {
    expect(numberLineMarkLabels([{ x: 1 }], (v) => v)).toEqual([]);
  });
});
