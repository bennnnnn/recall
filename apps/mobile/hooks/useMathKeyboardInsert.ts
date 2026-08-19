import { useCallback, useRef, useState } from "react";
import {
  Keyboard,
  type NativeSyntheticEvent,
  type TextInputSelectionChangeEventData,
} from "react-native";

import { clipboardIsImageOnly } from "@/lib/mathClipboard";
import {
  autoAdvanceFracDen,
  caretForInsert,
  fracTapAdvancesToDen,
  MATH_KEYBOARD_SYMBOLS,
  type MathKeyboardGroup,
  nextEditSlotCaret,
  prevEditSlotCaret,
  spliceMathInsert,
  type MathKeyboardSymbol,
  type TextSelection,
} from "@/lib/mathKeyboardSymbols";
import { applyPinnedTextChange } from "@/lib/mathComposerChange";
import { applyComposerTextChange, extractInsertedDelta } from "@/lib/mathPasteNormalize";
import { spliceMathBackspace, stepMathCaret } from "@/lib/mathDraftSlots";

export const MATH_PAD_FALLBACK_HEIGHT = 320;

export function useMathKeyboardInsert(options: {
  input: string;
  setInput: (text: string) => void;
  onImageOnlyPaste?: () => void;
}) {
  const { input, setInput, onImageOnlyPaste } = options;
  const [mathBarOpen, setMathBarOpen] = useState(false);
  const [mathGroup, setMathGroup] = useState<MathKeyboardGroup>("basics");
  const [padHeight, setPadHeight] = useState(MATH_PAD_FALLBACK_HEIGHT);
  const [selection, setSelection] = useState<TextSelection>({ start: 0, end: 0 });
  const [forcedSelection, setForcedSelection] = useState<TextSelection | undefined>();
  const pinRef = useRef<TextSelection | null>(null);
  const mathBarOpenRef = useRef(false);
  const textRef = useRef(input);
  textRef.current = input;

  const pinSelection = useCallback((sel: TextSelection) => {
    pinRef.current = sel;
    setSelection(sel);
    setForcedSelection(sel);
  }, []);

  const onSelectionChange = useCallback(
    (event: NativeSyntheticEvent<TextInputSelectionChangeEventData>) => {
      const next = event.nativeEvent.selection;
      const pinned = pinRef.current;
      // Preview caret is the source of truth whenever `$` is in the draft.
      // The parked TextInput keeps the OS caret in the last LaTeX slot.
      if (pinned && textRef.current.includes("$")) {
        if (next.start !== pinned.start || next.end !== pinned.end) {
          setForcedSelection({ ...pinned });
        }
        return;
      }
      pinRef.current = next;
      setSelection(next);
      setForcedSelection(undefined);
    },
    [],
  );

  const onChangeText = useCallback(
    (next: string) => {
      const pin = pinRef.current ?? selection;
      const replayed = applyPinnedTextChange(input, next, pin);
      const converted = applyComposerTextChange(input, replayed.text);
      const caret =
        converted === replayed.text
          ? replayed.caret
          : replayed.caret + (converted.length - replayed.text.length);
      textRef.current = converted;
      setInput(converted);
      pinSelection({ start: caret, end: caret });
      const delta = extractInsertedDelta(input, next);
      if (delta && onImageOnlyPaste) {
        void clipboardIsImageOnly().then((imageOnly) => {
          if (imageOnly) onImageOnlyPaste();
        });
      }
    },
    [input, onImageOnlyPaste, pinSelection, selection, setInput],
  );

  const closeMathBar = useCallback(() => {
    mathBarOpenRef.current = false;
    setMathBarOpen(false);
  }, []);

  const insertSymbol = useCallback(
    (spec: MathKeyboardSymbol) => {
      const sel = pinRef.current ?? selection;
      const text = textRef.current;
      if (spec.id === "frac") {
        const jump = fracTapAdvancesToDen(text, sel.start);
        if (jump != null) {
          pinSelection({ start: jump, end: jump });
          return;
        }
      }
      const at = caretForInsert(text, sel.start, spec);
      const insertAt = at === sel.start ? sel : { start: at, end: at };
      const result = spliceMathInsert(text, insertAt, spec);
      const advanced =
        at === sel.start
          ? autoAdvanceFracDen(text, sel.start, result.text, result.selection.start, spec)
          : null;
      const caret = advanced ?? result.selection.start;
      textRef.current = result.text;
      setInput(result.text);
      pinSelection({ start: caret, end: caret });
    },
    [pinSelection, selection, setInput],
  );

  const nextSlot = useCallback(() => {
    const sel = pinRef.current ?? selection;
    const jump = nextEditSlotCaret(textRef.current, sel.start);
    if (jump == null) return;
    pinSelection({ start: jump, end: jump });
  }, [pinSelection, selection]);

  const prevSlot = useCallback(() => {
    const sel = pinRef.current ?? selection;
    const jump = prevEditSlotCaret(textRef.current, sel.start);
    if (jump == null) return;
    pinSelection({ start: jump, end: jump });
  }, [pinSelection, selection]);

  const stepCaret = useCallback(
    (dir: -1 | 1) => {
      const sel = pinRef.current ?? selection;
      const next = stepMathCaret(textRef.current, sel.start, dir);
      pinSelection({ start: next, end: next });
    },
    [pinSelection, selection],
  );

  const backspace = useCallback(() => {
    const sel = pinRef.current ?? selection;
    const result = spliceMathBackspace(textRef.current, sel);
    textRef.current = result.text;
    setInput(result.text);
    pinSelection(result.selection);
  }, [pinSelection, selection, setInput]);

  const pasteText = useCallback(
    async (text: string) => {
      if (!text) return;
      const sel = pinRef.current ?? selection;
      const before = textRef.current.slice(0, sel.start);
      const after = textRef.current.slice(sel.end);
      const next = before + text + after;
      const caret = sel.start + text.length;
      textRef.current = next;
      setInput(next);
      pinSelection({ start: caret, end: caret });
    },
    [pinSelection, selection, setInput],
  );

  const moveCaret = useCallback(
    (pos: number) => {
      const next = Math.max(0, Math.min(pos, textRef.current.length));
      pinSelection({ start: next, end: next });
    },
    [pinSelection],
  );

  const toggleMathBar = useCallback(() => {
    if (mathBarOpen) {
      mathBarOpenRef.current = false;
      // Sit in front of `$...$` so ABC types words beside the formula, not
      // raw LaTeX inside a slot.
      pinSelection({ start: 0, end: 0 });
      setMathBarOpen(false);
      return;
    }
    const measured = Keyboard.metrics()?.height ?? 0;
    if (measured >= 200) setPadHeight(measured);
    Keyboard.dismiss();
    mathBarOpenRef.current = true;
    setMathBarOpen(true);
  }, [mathBarOpen, pinSelection]);

  return {
    mathBarOpen,
    padHeight,
    toggleMathBar,
    closeMathBar,
    mathGroup,
    setMathGroup,
    selection,
    forcedSelection,
    onSelectionChange,
    onChangeText,
    insertSymbol,
    backspace,
    pasteText,
    nextSlot,
    prevSlot,
    stepCaret,
    moveCaret,
    symbols: MATH_KEYBOARD_SYMBOLS,
  };
}
