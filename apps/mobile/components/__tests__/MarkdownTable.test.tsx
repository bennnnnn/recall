import { fireEvent, render } from "@testing-library/react-native";
import { Dimensions, Text } from "react-native";

import {
  MarkdownTable,
  MarkdownTableCell,
  MarkdownTableRow,
  tableShouldFreezeFirstColumn,
  tableViewportWidth,
  resolveFrozenRowHeight,
} from "@/components/MarkdownTable";
import { hiddenScrollEdges } from "@/components/markdown/FadingHorizontalScroll";
import {
  sumWidths,
  TABLE_MAX_COL_WIDTH,
  TABLE_MIN_COL_WIDTH,
  tableColumnText,
  TABLE_PEEK,
  tableColumnWidths,
  textWidthUnits,
  type TableColumnText,
} from "@/components/markdown/tableLayout";
import type { AstNode } from "@/components/markdown/markdownAstHelpers";

// A label column beside two long description columns (the phone/OS compare).
const COMPARE_COLUMNS: TableColumnText[] = [
  { longest: 13, longestWord: 13 },
  { longest: 56, longestWord: 12 },
  { longest: 56, longestWord: 13 },
];

describe("tableViewportWidth", () => {
  it("caps an intrinsic wide-table measurement to the phone canvas", () => {
    expect(tableViewportWidth(390, 672)).toBe(358);
  });

  it("retains a genuinely narrower measured message width", () => {
    expect(tableViewportWidth(390, 320)).toBe(320);
  });
});

describe("tableColumnText", () => {
  it("reads each column's longest cell and longest word, header included", () => {
    const cell = (type: string, text: string): AstNode => ({
      key: text,
      type,
      children: [{ key: `${text}-t`, type: "text", content: text }],
    });
    const row = (key: string, cells: AstNode[]): AstNode => ({ key, type: "tr", children: cells });
    const table: AstNode = {
      key: "t",
      type: "table",
      children: [
        { key: "h", type: "thead", children: [row("hr", [cell("th", "Area"), cell("th", "iPhone (iOS)")])] },
        { key: "b", type: "tbody", children: [row("br", [cell("td", "Customization"), cell("td", "Limited to widgets")])] },
      ],
    };
    expect(tableColumnText(table)).toEqual([
      { longest: 13, longestWord: 13 },
      { longest: 18, longestWord: 7 },
    ]);
  });
});

describe("tableColumnWidths", () => {
  it("keeps a short label column narrow beside long text, and pans", () => {
    const [label, ios, android] = tableColumnWidths(COMPARE_COLUMNS, 358);
    // Equal thirds gave "Customization" 168 pt; it needs about 128.
    expect(label).toBeLessThan(140);
    expect(label).toBeLessThan((label + ios + android) / 4);
    // The edge cut iOS: it narrows so Android's start shows, a sign the row scrolls.
    expect(label + ios).toBe(358 - TABLE_PEEK);
    expect(android).toBe(TABLE_MAX_COL_WIDTH);
    expect(label + ios + android).toBeGreaterThan(358);
  });

  it("shows the next column's start at the edge of a two-sided comparison", () => {
    // Live: "Feature | Mitosis | Meiosis" showed Mitosis cut at the edge and no Meiosis.
    const columns: TableColumnText[] = [
      { longest: 19, longestWord: 9 },
      { longest: 43, longestWord: 12 },
      { longest: 43, longestWord: 12 },
    ];
    const [feature, mitosis, meiosis] = tableColumnWidths(columns, 384);
    expect(feature + mitosis).toBe(384 - TABLE_PEEK);
    expect(mitosis).toBeGreaterThanOrEqual(12 * 8);
    expect(meiosis).toBe(TABLE_MAX_COL_WIDTH);
  });

  it("keeps a column's floor even when the next one cannot peek", () => {
    // The edge (250 - 48) cuts the first column, but its longest word needs 240.
    const [first, second] = tableColumnWidths(
      [{ longest: 30, longestWord: 30 }, { longest: 30, longestWord: 30 }],
      250,
    );
    expect(first).toBe(TABLE_MAX_COL_WIDTH);
    expect(second).toBe(TABLE_MAX_COL_WIDTH);
  });

  it("stretches a table that fits to the full width", () => {
    const widths = tableColumnWidths(
      [{ longest: 4, longestWord: 4 }, { longest: 3, longestWord: 3 }],
      358,
    );
    expect(sumWidths(widths)).toBeGreaterThan(350);
    expect(sumWidths(widths)).toBeLessThanOrEqual(358);
  });

  it("never draws a column narrower than its longest word or the floor", () => {
    const [tiny, word] = tableColumnWidths(
      [{ longest: 1, longestWord: 1 }, { longest: 60, longestWord: 18 }, { longest: 90, longestWord: 5 }],
      200,
    );
    expect(tiny).toBe(TABLE_MIN_COL_WIDTH);
    expect(word).toBeGreaterThanOrEqual(18 * 8);
  });

  it("gives a word room at the phone's larger text sizes", () => {
    // "Customization" at twice the size: 13 letters of about 16 pt, not 8.
    const column = { longest: 13, longestWord: 13 };
    const [normal] = tableColumnWidths([column, { longest: 60, longestWord: 8 }], 358);
    const [large] = tableColumnWidths([column, { longest: 60, longestWord: 8 }], 358, 2);
    expect(normal).toBeGreaterThanOrEqual(13 * 8);
    expect(large).toBeGreaterThanOrEqual(13 * 16);
    // A word wider than the old 240 ceiling still fits whole, up to the viewport.
    const [wide] = tableColumnWidths([{ longest: 20, longestWord: 20 }], 358, 2);
    expect(wide).toBeGreaterThanOrEqual(Math.min(20 * 16, 358));
  });
});

describe("textWidthUnits", () => {
  it("counts a CJK or Ethiopic character as two Latin letters, a mark as none", () => {
    expect(textWidthUnits("Price")).toEqual({ width: 5, longestWord: 5 });
    // Amharic words are spaced: "ዋጋ ከፍተኛ" is two words, the second four characters wide.
    expect(textWidthUnits("ዋጋ ከፍተኛ")).toEqual({ width: 13, longestWord: 8 });
    // Hindi's vowel signs are marks: "कीमत" draws as three letters.
    expect(textWidthUnits("कीमत").width).toBe(3);
  });

  it("lets Chinese and Japanese break between any two characters", () => {
    // One unspaced run of four Han characters: its widest piece is one character.
    expect(textWidthUnits("价格很高")).toEqual({ width: 8, longestWord: 2 });
    expect(textWidthUnits("値段 high")).toEqual({ width: 9, longestWord: 4 });
  });

  it("sizes an Amharic column for its characters, not their count", () => {
    const cell = (type: string, text: string): AstNode => ({
      key: text,
      type,
      children: [{ key: `${text}-t`, type: "text", content: text }],
    });
    const table: AstNode = {
      key: "t",
      type: "table",
      children: [{ key: "r", type: "tr", children: [cell("td", "ማብራሪያ"), cell("td", "x")] }],
    };
    const [column] = tableColumnText(table);
    // Five characters, ten Latin letters wide: 8 pt a character broke the word mid-letter.
    expect(column).toEqual({ longest: 10, longestWord: 10 });
    expect(tableColumnWidths([column!], 358)[0]).toBeGreaterThanOrEqual(10 * 8);
  });
});

describe("tableShouldFreezeFirstColumn", () => {
  it("pans the whole table when 3+ columns overflow a phone viewport", () => {
    const widths = tableColumnWidths(COMPARE_COLUMNS, 358);
    expect(tableShouldFreezeFirstColumn(3, 358, sumWidths(widths))).toBe(false);
  });

  it("freezes the first column on a tablet", () => {
    const five = Array.from({ length: 5 }, () => ({ longest: 60, longestWord: 10 }));
    const widths = tableColumnWidths(five, 768);
    expect(tableShouldFreezeFirstColumn(5, 768, sumWidths(widths))).toBe(true);
  });

  it("does not freeze a 2-column table", () => {
    expect(tableShouldFreezeFirstColumn(2, 358, 480)).toBe(false);
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

describe("hiddenScrollEdges", () => {
  it("reports content cut off past each edge", () => {
    expect(hiddenScrollEdges(0, 358, 600)).toEqual({ start: false, end: true });
    expect(hiddenScrollEdges(100, 358, 600)).toEqual({ start: true, end: true });
    expect(hiddenScrollEdges(242, 358, 600)).toEqual({ start: true, end: false });
  });
});

describe("MarkdownTable scroll cue", () => {
  // React Native's test window is at twice the text size; these read the default size.
  const testWindow = Dimensions.get("window");
  beforeEach(() => Dimensions.set({ window: { ...testWindow, fontScale: 1 } }));
  afterEach(() => Dimensions.set({ window: testWindow }));

  async function renderTable(columns: TableColumnText[]) {
    return render(
      <MarkdownTable nodeKey="t" columns={columns}>
        <MarkdownTableRow nodeKey="r">
          {columns.map((_, i) => (
            <MarkdownTableCell key={i} nodeKey={`c${i}`}>
              <Text>{`cell ${i}`}</Text>
            </MarkdownTableCell>
          ))}
        </MarkdownTableRow>
      </MarkdownTable>,
    );
  }

  async function renderCompare() {
    const utils = await renderTable(COMPARE_COLUMNS);
    // The chat column on a 390 pt phone.
    await fireEvent(utils.getByTestId("markdown-table"), "layout", {
      nativeEvent: { layout: { width: 358, height: 300 } },
    });
    return utils;
  }

  it("fades the clipped right edge of a wide table", async () => {
    const { getByTestId, queryByTestId } = await renderCompare();
    expect(getByTestId("scroll-fade-end")).toBeOnTheScreen();
    expect(queryByTestId("scroll-fade-start")).toBeNull();
  });

  it("moves the fade to the left edge once scrolled to the end", async () => {
    const { getByTestId, queryByTestId } = await renderCompare();
    const scroll = getByTestId("markdown-table-scroll");
    await fireEvent.scroll(scroll, {
      nativeEvent: {
        contentOffset: { x: 2000, y: 0 },
        contentSize: { width: 2000, height: 300 },
        layoutMeasurement: { width: 358, height: 300 },
      },
    });
    expect(queryByTestId("scroll-fade-end")).toBeNull();
    expect(getByTestId("scroll-fade-start")).toBeOnTheScreen();
  });

  it("draws no fade on a table that fits", async () => {
    const { getByTestId, queryByTestId } = await renderTable([
      { longest: 1, longestWord: 1 },
      { longest: 1, longestWord: 1 },
    ]);
    await fireEvent(getByTestId("markdown-table"), "layout", {
      nativeEvent: { layout: { width: 358, height: 80 } },
    });
    expect(queryByTestId("scroll-fade-end")).toBeNull();
    expect(getByTestId("markdown-table-scroll").props.scrollEnabled).toBe(false);
  });

  it("sizes each cell by its own column", async () => {
    const { getByText } = await renderCompare();
    // Text → cellInner → cell (the View that carries the column width).
    const widthOf = (text: string) => getByText(text).parent?.parent?.props.style;
    const [label, ios] = tableColumnWidths(COMPARE_COLUMNS, 358);
    expect(widthOf("cell 0")).toEqual(expect.arrayContaining([{ width: label }]));
    expect(widthOf("cell 1")).toEqual(expect.arrayContaining([{ width: ios }]));
  });
});
