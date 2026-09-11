import {
  ancestorTypeCount,
  immediateAncestorType,
  listItemDisplayNumber,
  listItemHasNestedList,
  shouldNumberListItem,
} from "@/components/markdown/markdownAstHelpers";

describe("nested list numbering", () => {
  it("does not number a top-level bullet list", () => {
    const parent = [{ type: "bullet_list" }];
    expect(immediateAncestorType(parent)).toBe("bullet_list");
    expect(ancestorTypeCount(parent, "bullet_list")).toBe(1);
    expect(shouldNumberListItem(parent)).toBe(false);
  });

  it("keeps bullets nested under another bullet list unordered", () => {
    const parent = [
      { type: "bullet_list" },
      { type: "list_item" },
      { type: "bullet_list" },
    ];
    expect(shouldNumberListItem(parent)).toBe(false);
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

describe("listItemHasNestedList", () => {
  it("is false for a leaf bullet", () => {
    expect(
      listItemHasNestedList({
        key: "a",
        type: "list_item",
        children: [{ key: "p", type: "paragraph", content: "Personalized" }],
      }),
    ).toBe(false);
  });

  it("is true when a topic item contains a nested bullet list", () => {
    expect(
      listItemHasNestedList({
        key: "a",
        type: "list_item",
        children: [
          { key: "p", type: "paragraph", content: "Strengths" },
          { key: "l", type: "bullet_list", children: [] },
        ],
      }),
    ).toBe(true);
  });
});
