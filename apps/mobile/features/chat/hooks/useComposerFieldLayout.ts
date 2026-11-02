import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  LayoutChangeEvent,
  NativeSyntheticEvent,
  TextInputContentSizeChangeEventData,
} from "react-native";

import type { ComposerTextSize } from "@/features/chat/components/ComposerTextMeasure";
import { useLatestRef } from "@/lib/latestRef";
import {
  COMPOSER_CONTROL_SIZE,
  composerInputFrameForLines,
  composerInputFrameHeight,
  composerInputMetrics,
  composerInputTextBoxHeight,
  composerSoftWrapLineCount,
  retainedComposerContentHeight,
} from "@/features/chat/model/composerLogic";

type Options = {
  input: string;
  /** Bumps on a thread switch: the next draft does not inherit this one's wrap height. */
  draftRevision: number | undefined;
  /** Native text scales the field's line box with the system text size. */
  fontScale: number;
  /** Extra field height past one line, so the thread moves up with the pill. */
  onInputFrameExtraChange?: (extra: number) => void;
};

/**
 * How tall the composer field is and the full-height editor toggle. The field
 * has the composer's full width, over the row of buttons (November 2026: beside
 * them, the placeholder wrapped on a narrow phone). The field reports its width
 * and content size; everything else is derived from the draft and the text size.
 */
export function useComposerFieldLayout({
  input,
  draftRevision,
  fontScale,
  onInputFrameExtraChange,
}: Options) {
  const [inputHeight, setInputHeight] = useState<number>(COMPOSER_CONTROL_SIZE);
  const [inputContentWidth, setInputContentWidth] = useState(0);
  const [composerExpanded, setComposerExpanded] = useState(false);
  // The off-screen copy's height at the field width: only another line renders again.
  const [measuredHeight, setMeasuredHeight] = useState(0);
  // Copies of state for the setters below, which skip a value React already
  // has (setting even an unchanged value right after a render renders again).
  const inputHeightRef = useRef(inputHeight);
  const measuredHeightRef = useRef(measuredHeight);
  const [measuredContent, setMeasuredContent] = useState<{ revision: number; height: number } | null>(null);
  // The effect below runs on the draft, not on each measurement: it reads the latest one.
  const measuredContentRef = useLatestRef(measuredContent);
  // The glyph estimate walks every character: once per draft and width, shared below.
  const estimatedLines = useMemo(
    () => composerSoftWrapLineCount(input, inputContentWidth, fontScale),
    [input, inputContentWidth, fontScale],
  );

  const commitInputHeight = useCallback((height: number) => {
    if (inputHeightRef.current === height) return;
    inputHeightRef.current = height;
    setInputHeight(height);
  }, []);

  // Expanded chrome belongs to the active draft, not the mounted screen.
  useEffect(() => {
    setComposerExpanded(false);
  }, [draftRevision]);

  useEffect(() => {
    // iOS can retain the last multiline content size after a controlled
    // TextInput is cleared. Pin the empty draft back to the single-line
    // height so a sent long message cannot leave a tall blank composer.
    // Within one draft, keep the last wrap height: a keystroke changes the
    // string without a new content-size event. A thread switch (revision)
    // drops that sample so the next draft does not inherit it.
    const revision = draftRevision ?? 0;
    if (!input) {
      setMeasuredContent(null);
      commitInputHeight(COMPOSER_CONTROL_SIZE);
      setComposerExpanded(false);
      return;
    }
    const retained = retainedComposerContentHeight(measuredContentRef.current, revision, input);
    const frame = composerInputFrameHeight(
      input,
      retained,
      inputContentWidth,
      fontScale,
      estimatedLines,
    );
    commitInputHeight(frame.height);
  }, [commitInputHeight, draftRevision, estimatedLines, fontScale, input, inputContentWidth, measuredContentRef]);

  const onTextMeasure = (size: ComposerTextSize) => {
    if (measuredHeightRef.current === size.height) return;
    measuredHeightRef.current = size.height;
    setMeasuredHeight(size.height);
  };

  // Only hard returns move the thread. A soft wrap grows the field in place;
  // pushing list padding here is what yanks the chat up on every line.
  // Measured from the one-line field COMPOSER_HEIGHT assumes, so a taller line
  // at a large text size moves the thread too. The button row is in COMPOSER_HEIGHT.
  const returnFrame = composerInputFrameHeight(input, 0, 0, fontScale);
  const inputFrameExtra = composerExpanded
    ? 0
    : Math.max(0, returnFrame.height - COMPOSER_CONTROL_SIZE);
  // Reported while the drawer hides the composer too: it keeps its size there,
  // so opening the drawer does not lay out the chat under it again.
  useEffect(() => {
    onInputFrameExtraChange?.(inputFrameExtra);
  }, [inputFrameExtra, onInputFrameExtraChange]);

  const measuredNow = input
    ? retainedComposerContentHeight(measuredContent, draftRevision ?? 0, input)
    : 0;
  const field = composerInputMetrics(fontScale);
  const frameNow =
    measuredHeight > 0
      ? composerInputFrameForLines(Math.round(measuredHeight / field.line), fontScale)
      : composerInputFrameHeight(
          input,
          Math.max(measuredNow, inputHeight),
          inputContentWidth,
          fontScale,
          estimatedLines,
        );
  // Same render as the keystroke. Waiting for the effect leaves one frame
  // clipped at the end of the line.
  const fieldHeight = input ? frameNow.height : field.min;
  const fieldOverflows = Boolean(input) && frameNow.overflows;

  const onInputLayout = (event: LayoutChangeEvent) => {
    const next = Math.round(event.nativeEvent.layout.width);
    if (next <= 0) return;
    setInputContentWidth((current) => (current === next ? current : next));
  };

  const onInputContentSizeChange = (
    event: NativeSyntheticEvent<TextInputContentSizeChangeEventData>,
  ) => {
    const measuredHeight = Math.ceil(event.nativeEvent.contentSize.height);
    const revision = draftRevision ?? 0;
    // An unchanged height keeps the same object: no render for a keystroke on the same line.
    setMeasuredContent((current) =>
      current?.revision === revision && current.height === measuredHeight ? current : { revision, height: measuredHeight },
    );
    const frame = composerInputFrameHeight(
      input,
      measuredHeight,
      inputContentWidth,
      fontScale,
      estimatedLines,
    );
    if (!composerExpanded) commitInputHeight(frame.height);
  };

  return {
    composerExpanded,
    toggleExpanded: () => setComposerExpanded((expanded) => !expanded),
    inputContentWidth,
    onTextMeasure,
    field,
    fieldHeight,
    // Text box matches the lines. Centering slack stays on the wrapper so one
    // line sits on the field's midline.
    textBoxHeight: composerInputTextBoxHeight(fieldHeight, fontScale),
    fieldOverflows,
    showExpandControl: fieldOverflows || composerExpanded,
    onInputLayout,
    onInputContentSizeChange,
  };
}
