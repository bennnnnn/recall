export {
  MATH_KEYBOARD_GROUPS,
  MATH_KEYBOARD_SYMBOLS,
  MATH_PAD_KEYS,
  SYMBOL_A11Y,
  isCursorInsideInlineMath,
  spliceMathInsert,
  symbolA11yLabel,
  type MathKeyboardGroup,
  type MathKeyboardSymbol,
  type TextSelection,
} from "@/lib/math/keyboardCatalog";
export {
  autoAdvanceNextEmptySlot,
  caretInGroup,
  findFracSlots,
  findLognSlots,
  findNrootSlots,
  innermostSlot,
  readBraceGroup,
  readDelimGroup,
  readSetBrace,
  tapAdvancesToNextSlot,
  type LatexGroup,
} from "@/lib/math/keyboardSlots";
export {
  PAD_ROWS,
  padRows,
  type PadCell,
  type SymbolPage,
} from "@/lib/math/keyboardPages";
export { caretStepLeft, caretStepRight } from "@/lib/math/caretStops";
