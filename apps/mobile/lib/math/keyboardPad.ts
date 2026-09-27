import { Space } from "@/lib/space";
import {
  MATH_NUMPAD_ROWS,
  MATH_SYMBOL_ROW_SIZE,
  symbolsInGroup,
  type MathKeyboardGroup,
} from "@/lib/math/keyboardSymbols";

/** Vertical padding inside the gray pad (8 top + 12 bottom). */
export const PAD_PADDING_V = 20;
export const PAD_GAP = 6;
export const KEY_HEIGHT_MIN = Space.minTouch;

const SYMBOL_GROUPS: MathKeyboardGroup[] = ["basics", "trig", "calc", "greek"];

function symbolRows(group: MathKeyboardGroup): number {
  if (group === "basics") return 4;
  return Math.ceil(symbolsInGroup(group).length / MATH_SYMBOL_ROW_SIZE) + 1;
}

/** Tallest symbol tab, including its 123 / delete row. Calc is 6 today. */
export function densestKeyRows(): number {
  return Math.max(MATH_NUMPAD_ROWS.length + 1, ...SYMBOL_GROUPS.map(symbolRows));
}

export const CONVERTER_VALUE_HEIGHT = 28;
export const CONVERTER_UNIT_HEIGHT = Space.minTouch;
export const CONVERTER_HEADER_HEIGHT = CONVERTER_VALUE_HEIGHT + PAD_GAP + CONVERTER_UNIT_HEIGHT;
export const CONVERTER_ROWS = 4;

function symbolPadHeight(tab: number, rows: number): number {
  return PAD_PADDING_V + tab + rows * KEY_HEIGHT_MIN + rows * PAD_GAP;
}

function converterPadHeight(tab: number): number {
  const keys =
    CONVERTER_HEADER_HEIGHT + CONVERTER_ROWS * KEY_HEIGHT_MIN + CONVERTER_ROWS * PAD_GAP;
  return PAD_PADDING_V + tab + PAD_GAP + keys;
}

/**
 * Gray pad tall enough that every key stays at least 44pt. A measured keyboard
 * taller than that still wins, so the keys grow instead of leaving a gap.
 */
export function mathPadHeight(measured: number, tabHeight: number = KEY_HEIGHT_MIN): number {
  const tab = Math.max(tabHeight, KEY_HEIGHT_MIN);
  return Math.max(measured, symbolPadHeight(tab, densestKeyRows()), converterPadHeight(tab));
}

export function fillKeyHeight(padHeight: number, tabHeight: number, keyRows: number): number {
  if (keyRows <= 0) return KEY_HEIGHT_MIN;
  const tab = Math.max(tabHeight, KEY_HEIGHT_MIN);
  const inner = padHeight - PAD_PADDING_V - tab - keyRows * PAD_GAP;
  return Math.max(KEY_HEIGHT_MIN, Math.floor(inner / keyRows));
}

export function converterKeyHeight(keysHeight: number): number {
  const chrome = CONVERTER_HEADER_HEIGHT + CONVERTER_ROWS * PAD_GAP;
  const room = keysHeight - chrome;
  if (room <= 0) return KEY_HEIGHT_MIN;
  return Math.max(KEY_HEIGHT_MIN, Math.floor(room / CONVERTER_ROWS));
}
