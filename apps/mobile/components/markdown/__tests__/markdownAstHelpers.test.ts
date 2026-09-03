import {
  ancestorTypeCount,
  immediateAncestorType,
  listItemDisplayNumber,
  shouldNumberListItem,
} from "@/components/markdown/markdownAstHelpers";

describe("nested list numbering", () => {
  it("does not number a top-level bullet list", () => {
    const parent = [{ type: "bullet_list" }];
    expect(immediateAncestorType(parent)).toBe("bullet_list");
    expect(ancestorTypeCount(parent, "bullet_list")).toBe(1);
    expect(shouldNumberListItem(parent)).toBe(false);
  });

  it("numbers bullets nested under another bullet list", () => {
    const parent = [
      { type: "bullet_list" },
      { type: "list_item" },
      { type: "bullet_list" },
    ];
    expect(shouldNumberListItem(parent)).toBe(true);
    expect(listItemDisplayNumber(parent, 0)).toBe(1);
    expect(listItemDisplayNumber(parent, 1)).toBe(2);
  });

  it("numbers a real ordered list even when it sits under a bullet", () => {
    const parent = [
      { type: "ordered_list", attributes: { start: 3 } },
      { type: "list_item" },
      { type: "bullet_list" },
    ];
    expect(shouldNumberListItem(parent)).toBe(true);
    expect(listItemDisplayNumber(parent, 0)).toBe(3);
  });
});
