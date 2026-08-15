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
  nextEditSlotCaret,
  spliceMathInsert,
  type MathKeyboardSymbol,
  type TextSelection,
} from "@/lib/mathKeyboardSymbols";
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
  const [padHeight, setPadHeight] = useState(MATH_PAD_FALLBACK_HEIGHT);
  const [selection, setSelection] = useState<TextSelection>({ start: 0, end: 0 });
  const [forcedSelection, setForcedSelection] = useState<TextSelection | undefined>();
  const pinRef = useRef<TextSelection | null>(null);
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
      if (pinned) {
        if (next.start !== pinned.start || next.end !== pinned.end) {
          setForcedSelection({ ...pinned });
        }
        return;
      }
      setSelection(next);
      setForcedSelection(undefined);
    },
    [],
  );

  const onChangeText = useCallback(
    (next: string) => {
      const delta = extractInsertedDelta(input, next);
      const converted = applyComposerTextChange(input, next);
      setInput(converted);
      if (delta && converted !== next) {
        const prefixLen = (() => {
          let i = 0;
          const minLen = Math.min(input.length, next.length);
          while (i < minLen && input[i] === next[i]) i += 1;
          return i;
        })();
        const caretPos = prefixLen + (converted.length - (next.length - delta.length));
        pinSelection({ start: caretPos, end: caretPos });
      }
      if (delta && onImageOnlyPaste) {
        void clipboardIsImageOnly().then((imageOnly) => {
          if (imageOnly) onImageOnlyPaste();
        });
      }
    },
    [input, onImageOnlyPaste, pinSelection, setInput],
  );

  const onComposerFocus = useCallback(() => {
    if (!onImageOnlyPaste) return;
    void clipboardIsImageOnly().then((imageOnly) => {
      if (imageOnly) onImageOnlyPaste();
    });
  }, [onImageOnlyPaste]);

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

  const moveCaret = useCallback(
    (pos: number) => {
      const next = Math.max(0, Math.min(pos, textRef.current.length));
      pinSelection({ start: next, end: next });
    },
    [pinSelection],
  );

  const toggleMathBar = useCallback(() => {
    if (mathBarOpen) {
      pinRef.current = null;
      setMathBarOpen(false);
      return;
    }
    const measured = Keyboard.metrics()?.height ?? 0;
    if (measured >= 200) setPadHeight(measured);
    Keyboard.dismiss();
    setMathBarOpen(true);
  }, [mathBarOpen]);

  return {
    mathBarOpen,
    padHeight,
    toggleMathBar,
    selection,
    forcedSelection,
    onSelectionChange,
    onChangeText,
    onComposerFocus,
    insertSymbol,
    backspace,
    nextSlot,
    stepCaret,
    moveCaret,
    symbols: MATH_KEYBOARD_SYMBOLS,
  };
}
