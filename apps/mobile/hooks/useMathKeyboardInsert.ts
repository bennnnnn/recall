import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  Keyboard,
  type NativeSyntheticEvent,
  type TextInputSelectionChangeEventData,
} from "react-native";

import { clipboardIsImageOnly } from "@/lib/math/mathClipboard";
import {
  autoAdvanceNextEmptySlot,
  caretForInsert,
  MATH_KEYBOARD_SYMBOLS,
  type MathKeyboardGroup,
  nextEditSlotCaret,
  prevEditSlotCaret,
  spliceMathInsert,
  tapAdvancesToNextSlot,
  type MathKeyboardSymbol,
  type TextSelection,
} from "@/lib/mathKeyboardSymbols";
import { applyPinnedTextChange, caretAfterMathBarClose, nativeEditRange } from "@/lib/math/mathComposerChange";
import {
  extractInsertedDelta,
  isMostlyProsePaste,
  shouldProbeClipboardForImagePaste,
  normalizePastedMath,
} from "@/lib/mathPasteNormalize";
import { spliceMathBackspace, stepMathCaret } from "@/lib/mathDraftSlots";

export const MATH_PAD_FALLBACK_HEIGHT = 320;

function hasEditableMath(text: string): boolean {
  return text.includes("$") && !isMostlyProsePaste(text);
}

export function useMathKeyboardInsert(options: {
  input: string;
  draftRevision?: number;
  setInput: (text: string) => void;
  onImageOnlyPaste?: () => void;
}) {
  const { input, setInput, onImageOnlyPaste, draftRevision = 0 } = options;
  const [mathBarOpen, setMathBarOpen] = useState(false);
  const [mathGroup, setMathGroup] = useState<MathKeyboardGroup>("basics");
  const [padHeight, setPadHeight] = useState(MATH_PAD_FALLBACK_HEIGHT);
  const [selection, setSelection] = useState<TextSelection>({ start: 0, end: 0 });
  const [forcedSelection, setForcedSelection] = useState<TextSelection | undefined>();
  const [previewEnabled, setPreviewEnabled] = useState(false);
  const previewEnabledRef = useRef(false);
  const draftRevisionRef = useRef(draftRevision);
  const pinRef = useRef<TextSelection | null>(null);
  const mathBarOpenRef = useRef(false);
  const textRef = useRef(input);
  textRef.current = input;

  const enablePreview = useCallback(() => {
    previewEnabledRef.current = true;
    setPreviewEnabled(true);
  }, []);

  useEffect(() => {
    if (input) return;
    previewEnabledRef.current = false;
    setPreviewEnabled(false);
  }, [input]);

  useLayoutEffect(() => {
    if (draftRevisionRef.current === draftRevision) return;
    draftRevisionRef.current = draftRevision;
    previewEnabledRef.current = false;
    setPreviewEnabled(false);
    mathBarOpenRef.current = false;
    setMathBarOpen(false);
    pinRef.current = null;
    setSelection({ start: input.length, end: input.length });
    setForcedSelection(undefined);
  }, [draftRevision, input]);

  const pinSelection = useCallback((sel: TextSelection) => {
    pinRef.current = sel;
    setSelection(sel);
    setForcedSelection(sel);
  }, []);

  const onSelectionChange = useCallback(
    (event: NativeSyntheticEvent<TextInputSelectionChangeEventData>) => {
      const next = event.nativeEvent.selection;
      const pinned = pinRef.current;
      // Only explicit math edits use the preview caret. Ordinary typing,
      // including dollar signs and formulas, keeps the native caret.
      // The parked TextInput keeps the OS caret in the last LaTeX slot.
      if (pinned && previewEnabledRef.current && hasEditableMath(textRef.current)) {
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
      const previous = textRef.current;
      const pin = pinRef.current ?? selection;
      const parked = previewEnabledRef.current && hasEditableMath(previous);
      // onChangeText does not identify a paste. Rewriting its delta can
      // corrupt ordinary/coalesced typing and race the native selection.
      const range = nativeEditRange(previous, next);
      const changed = parked
        ? applyPinnedTextChange(previous, next, pin)
        : { text: next, caret: range ? range.at + range.added.length : pin.start };
      textRef.current = changed.text;
      setInput(changed.text);
      const nextSelection = { start: changed.caret, end: changed.caret };
      if (parked) {
        pinSelection(nextSelection);
      } else {
        pinRef.current = nextSelection;
        setSelection(nextSelection);
        setForcedSelection(undefined);
      }
      if (!changed.text) {
        previewEnabledRef.current = false;
        setPreviewEnabled(false);
      }
      const delta = extractInsertedDelta(previous, next);
      if (delta && onImageOnlyPaste && shouldProbeClipboardForImagePaste(delta)) {
        void clipboardIsImageOnly().then((imageOnly) => {
          if (imageOnly) onImageOnlyPaste();
        });
      }
    },
    [onImageOnlyPaste, pinSelection, selection, setInput],
  );

  const closeMathBar = useCallback(() => {
    mathBarOpenRef.current = false;
    setMathBarOpen(false);
  }, []);

  const insertSymbol = useCallback(
    (spec: MathKeyboardSymbol) => {
      enablePreview();
      const sel = pinRef.current ?? selection;
      const text = textRef.current;
      const jump = tapAdvancesToNextSlot(text, sel.start, spec.id);
      if (jump != null) {
        pinSelection({ start: jump, end: jump });
        return;
      }
      const at = caretForInsert(text, sel.start, spec);
      const insertAt = at === sel.start ? sel : { start: at, end: at };
      const result = spliceMathInsert(text, insertAt, spec);
      const advanced =
        at === sel.start
          ? autoAdvanceNextEmptySlot(text, sel.start, result.text, result.selection.start, spec)
          : null;
      const caret = advanced ?? result.selection.start;
      textRef.current = result.text;
      setInput(result.text);
      pinSelection({ start: caret, end: caret });
    },
    [enablePreview, pinSelection, selection, setInput],
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
      enablePreview();
      const sel = pinRef.current ?? selection;
      const before = textRef.current.slice(0, sel.start);
      const after = textRef.current.slice(sel.end);
      const convertedChunk = normalizePastedMath(text);
      const spliced = before + convertedChunk + after;
      const caret = before.length + convertedChunk.length;
      textRef.current = spliced;
      setInput(spliced);
      pinSelection({ start: caret, end: caret });
    },
    [enablePreview, pinSelection, selection, setInput],
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
      const text = textRef.current;
      const caret = caretAfterMathBarClose(text);
      pinSelection({ start: caret, end: caret });
      setMathBarOpen(false);
      return;
    }
    const measured = Keyboard.metrics()?.height ?? 0;
    if (hasEditableMath(textRef.current)) enablePreview();
    if (measured >= 200) setPadHeight(measured);
    Keyboard.dismiss();
    mathBarOpenRef.current = true;
    setMathBarOpen(true);
  }, [enablePreview, mathBarOpen, pinSelection]);

  return {
    mathBarOpen,
    showMathPreview: draftRevisionRef.current === draftRevision && previewEnabled && hasEditableMath(input),
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
