import {
  CONVERTER_HEADER_HEIGHT,
  CONVERTER_ROWS,
  KEY_HEIGHT_MIN,
  PAD_GAP,
  PAD_PADDING_V,
  converterKeyHeight,
  densestKeyRows,
  fillKeyHeight,
  mathPadHeight,
} from "@/lib/math/keyboardPad";

describe("math pad height", () => {
  it("keeps the densest keypad and the converter at least 44pt", () => {
    const pad = mathPadHeight(320);
    const rows = densestKeyRows();
    const key = fillKeyHeight(pad, KEY_HEIGHT_MIN, rows);
    const keysBox = pad - PAD_PADDING_V - KEY_HEIGHT_MIN - PAD_GAP;
    const converter = converterKeyHeight(keysBox);

    expect(pad).toBeGreaterThanOrEqual(320);
    expect(key).toBeGreaterThanOrEqual(KEY_HEIGHT_MIN);
    expect(converter).toBeGreaterThanOrEqual(KEY_HEIGHT_MIN);
    expect(KEY_HEIGHT_MIN * rows + rows * PAD_GAP).toBeLessThanOrEqual(
      pad - PAD_PADDING_V - KEY_HEIGHT_MIN,
    );
    expect(
      CONVERTER_HEADER_HEIGHT + CONVERTER_ROWS * PAD_GAP + converter * CONVERTER_ROWS,
    ).toBeLessThanOrEqual(keysBox);
  });

  it("grows with a taller measured keyboard", () => {
    expect(mathPadHeight(480)).toBe(480);
  });
});
