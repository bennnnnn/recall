import { useEffect, useState } from "react";
import type {
  LayoutChangeEvent,
  NativeSyntheticEvent,
  TextInputContentSizeChangeEventData,
} from "react-native";

import type { ComposerTextSize } from "@/features/chat/components/ComposerTextMeasure";
import {
  COMPOSER_CONTROL_SIZE,
  composerInputFrameForLines,
  composerInputFrameHeight,
  composerInputMetrics,
  composerInputTextBoxHeight,
  composerSoftWrapLineCount,
  retainedComposerContentHeight,
} from "@/features/chat/model/composerLogic";
import { useLatestRef } from "@/lib/latestRef";

type Options = {
  input: string;
  /** Bumps on a thread switch: the next draft does not inherit this one's wrap height. */
  draftRevision: number | undefined;
  /** Native text scales the field's line box with the system text size. */
  fontScale: number;
  visible: boolean;
  /** Recording or transcribing: the waveform takes the row, so nothing stacks. */
  voiceActive: boolean;
  /** Extra field height past one line, so the thread moves up with the pill. */
  onInputFrameExtraChange?: (extra: number) => void;
};

/**
 * How tall the composer field is, whether its text wraps above the buttons,
 * and the full-height editor toggle. The field reports its width and content
 * size; everything else is derived from the draft and the text size.
 */
export function useComposerFieldLayout({
  input,
  draftRevision,
  fontScale,
  visible,
  voiceActive,
  onInputFrameExtraChange,
}: Options) {
  const [inputHeight, setInputHeight] = useState<number>(COMPOSER_CONTROL_SIZE);
  const [inputContentWidth, setInputContentWidth] = useState(0);
  const [composerExpanded, setComposerExpanded] = useState(false);
  // Field width beside the buttons. Wrapping is judged at this width, so the
  // wider stacked field cannot flip the layout back.
  const [inlineWidth, setInlineWidth] = useState(0);
  const [textSize, setTextSize] = useState<ComposerTextSize>({ naturalWidth: 0, height: 0 });
  const [measuredContent, setMeasuredContent] = useState<{ revision: number; height: number } | null>(null);
  // The effect below runs on the draft, not on each measurement: it reads the latest one.
  const measuredRef = useLatestRef(measuredContent);

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
      setInputHeight(COMPOSER_CONTROL_SIZE);
      setComposerExpanded(false);
      return;
    }
    const measured = retainedComposerContentHeight(
      measuredRef.current,
      revision,
      input,
    );
    const frame = composerInputFrameHeight(input, measured, inputContentWidth, fontScale);
    setInputHeight(frame.height);
  }, [draftRevision, fontScale, input, inputContentWidth, measuredRef]);

  // Only hard returns move the thread. A soft wrap grows the field in place;
  // pushing list padding here is what yanks the chat up on every line.
  // Measured from the 44 pt field COMPOSER_HEIGHT assumes, so a taller line
  // at a large text size moves the thread too.
  const returnFrame = composerInputFrameHeight(input, 0, 0, fontScale);
  // Text wraps beside the buttons: it takes the full width over a row of them.
  // Judged on the rendered text; the glyph estimate is only for the first frame.
  const stacked = Boolean(input) && (
    input.includes("\n") ||
    (textSize.naturalWidth > 0
      ? inlineWidth > 0 && textSize.naturalWidth > inlineWidth
      : composerSoftWrapLineCount(input, inlineWidth, fontScale) > 1)
  );
  // Stacking adds the button row once, so the last reply stays clear of the pill.
  const inputFrameExtra = composerExpanded
    ? 0
    : Math.max(0, returnFrame.height - COMPOSER_CONTROL_SIZE) +
      (stacked ? COMPOSER_CONTROL_SIZE : 0);
  useEffect(() => {
    onInputFrameExtraChange?.(visible ? inputFrameExtra : 0);
  }, [inputFrameExtra, onInputFrameExtraChange, visible]);

  const measuredNow = input
    ? retainedComposerContentHeight(measuredContent, draftRevision ?? 0, input)
    : 0;
  const field = composerInputMetrics(fontScale);
  const frameNow =
    textSize.height > 0
      ? composerInputFrameForLines(Math.round(textSize.height / field.line), fontScale)
      : composerInputFrameHeight(
          input,
          Math.max(measuredNow, inputHeight),
          inputContentWidth,
          fontScale,
        );
  // Same render as the keystroke. Waiting for the effect leaves one frame
  // clipped at the end of the line.
  const fieldHeight = input ? frameNow.height : field.min;
  const fieldOverflows = Boolean(input) && frameNow.overflows;
  const stackedLayout = (stacked || composerExpanded) && !voiceActive;

  const onInputLayout = (event: LayoutChangeEvent) => {
    const next = Math.round(event.nativeEvent.layout.width);
    if (next <= 0) return;
    setInputContentWidth((current) => (current === next ? current : next));
    if (!stackedLayout) setInlineWidth(next);
  };

  const onInputContentSizeChange = (
    event: NativeSyntheticEvent<TextInputContentSizeChangeEventData>,
  ) => {
    const measured = Math.ceil(event.nativeEvent.contentSize.height);
    const revision = draftRevision ?? 0;
    setMeasuredContent((current) =>
      current?.revision === revision && current.height === measured ? current : { revision, height: measured },
    );
    const frame = composerInputFrameHeight(
      input,
      measured,
      inputContentWidth,
      fontScale,
    );
    if (!composerExpanded) {
      setInputHeight((current) =>
        current === frame.height ? current : frame.height,
      );
    }
  };

  return {
    composerExpanded,
    toggleExpanded: () => setComposerExpanded((expanded) => !expanded),
    inputContentWidth,
    setTextSize,
    field,
    fieldHeight,
    // Text box matches the lines. Centering slack stays on the wrapper so the
    // caret remains on the last line, beside the buttons.
    textBoxHeight: composerInputTextBoxHeight(fieldHeight, fontScale),
    fieldOverflows,
    singleLineComposer: !composerExpanded && fieldHeight <= field.min,
    showExpandControl: fieldOverflows || composerExpanded,
    stackedLayout,
    onInputLayout,
    onInputContentSizeChange,
  };
}
