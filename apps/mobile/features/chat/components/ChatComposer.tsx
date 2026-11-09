import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
  type ViewStyle,
  type TextInputInstance,
} from "react-native";
import Animated, {
  useAnimatedStyle,
  type AnimatedStyle,
  type SharedValue,
} from "react-native-reanimated";
import { LinearGradient } from "expo-linear-gradient";
import {
  BOTTOM_CHROME_FADE_LOCATIONS,
  bottomChromeFadeColors,
  COMPOSER_GAP_FADE_LOCATIONS,
  composerGapFadeColors,
} from "@/features/chat/components/chromeFade";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { type MeterLevel, VoiceComposerWaveform } from "@/features/speech/components/VoiceComposerWaveform";
import {
  MathDraftPreview,
  MATH_DRAFT_PREVIEW_HEIGHT,
} from "@/features/chat/components/MathDraftPreview";
import {
  ComposerAttachButton,
  ComposerExpandControl,
  ComposerPlaceholder,
  useComposerPrompt,
  ComposerScanHint,
  COMPOSER_SCAN_HINT_HEIGHT,
} from "@/features/chat/components/ComposerControls";
import { ComposerSendControls } from "@/features/chat/components/ComposerSendControls";
import { ComposerTextMeasure } from "@/features/chat/components/ComposerTextMeasure";
import { MathComposerCaret } from "@/features/chat/components/MathComposerCaret";
import { MathKeyboardBar } from "@/features/chat/components/MathKeyboardBar";
import { liveAnswerShows, MATH_LIVE_ANSWER_HEIGHT, MathLiveAnswer } from "@/features/chat/components/MathLiveAnswer";
import { makeChatComposerStyles } from "@/features/chat/components/chatComposerStyles";
import { ComposerAttachmentPreview } from "@/features/attachments/components/ComposerAttachmentPreview";
import {
  useComposerDraftApiOptional,
  useComposerDraftValueOptional,
} from "@/features/chat/context/ComposerDraftContext";
import { useAuthToken } from "@/contexts/AuthContext";
import { useComposerFieldLayout } from "@/features/chat/hooks/useComposerFieldLayout";
import { useComposerRowFit } from "@/features/chat/hooks/useComposerRowFit";
import { useMathKeyboardInsert, useMathKeyboardRequests } from "@/features/chat/hooks/useMathKeyboardInsert";
import { useMathPadField } from "@/features/chat/hooks/useMathPadField";
import type { PendingAttachment } from "@/features/attachments/model/attachments";
import {
  CHAT_COMPOSER_MIN_BOTTOM_PAD,
  COMPOSER_CONTROL_SIZE,
  COMPOSER_GAP_FADE_OVERLAP,
  composerNativeInputTraits,
  composerShowsMic,
  composerShowsSend,
} from "@/features/chat/model/composerLogic";
import { pasteClipboardText } from "@/lib/clipboard";
import { caretAfterExpression, caretBeforeExpression } from "@/lib/math/draftSlots";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import { DYNAMIC_TYPE_MAX } from "@/lib/type";

function noopComposerInput(_text: string) {}
function noopOpen() {}

// One 36 pt row (+, the field, mic and live talk) + the card's 1 pt border and 4 pt padding
// above and below + 6 pt shell air above and below.
export const COMPOSER_HEIGHT = COMPOSER_CONTROL_SIZE + 22;
const COMPOSER_STATUS_LINE_HEIGHT = 18;

type Props = {
  visible: boolean;
  animatedContainerStyle?: AnimatedStyle<ViewStyle>;
  /** The keyboard's height, frame by frame (the chat's corrected keyboard). */
  keyboardHeight?: SharedValue<number>;
  streaming: boolean;
  /** A picked file is still being prepared: Send and Attach wait for it. */
  attachPicking?: boolean;
  sendBusy?: boolean;
  sendStatus?: string;
  pendingAttachment: PendingAttachment | null;
  onRemoveAttachment: () => void;
  onCloseAttachSheet: () => void;
  onPickAttachment: () => void;
  onSend: (text?: string) => void;
  onStop: () => void;
  isOffline: boolean;
  voiceAvailable?: boolean;
  voiceRecording?: boolean;
  voiceTranscribing?: boolean;
  voiceMeterLevel?: MeterLevel;
  onVoicePress?: () => void;
  /** Drops the open mic take, including a transcription already in flight. */
  onCancelVoice?: () => void;
  onLiveTalkPress?: () => void;
  /**
   * A live talk call is up, from connecting to hang-up: the composer is not drawn (the
   * call's own mute and end buttons take the row). The draft stays in its context.
   */
  liveTalkActive?: boolean;
  onOpenMathScanner?: () => void;
  onMathChromeHeightChange?: (height: number, padHeight: number) => void;
  /** Extra field height past one line, so the thread moves up with the pill. */
  onInputFrameExtraChange?: (extra: number) => void;
};

export const ChatComposer = memo(function ChatComposer({
  visible,
  animatedContainerStyle,
  keyboardHeight,
  streaming,
  attachPicking = false,
  sendBusy = false,
  sendStatus,
  pendingAttachment,
  onRemoveAttachment,
  onCloseAttachSheet,
  onPickAttachment,
  onSend,
  onStop,
  isOffline,
  voiceAvailable = false,
  voiceRecording = false,
  voiceTranscribing = false,
  voiceMeterLevel,
  onVoicePress,
  onCancelVoice,
  onLiveTalkPress,
  liveTalkActive = false,
  onOpenMathScanner,
  onMathChromeHeightChange,
  onInputFrameExtraChange,
}: Props) {
  const prompt = useComposerPrompt();
  const token = useAuthToken();
  const insets = useSafeAreaInsets();
  // Native text scales the field's line box with the system text size.
  const { fontScale } = useWindowDimensions();
  const theme = useTheme();
  const s = useMemo(() => makeChatComposerStyles(theme), [theme]);
  const draft = useComposerDraftValueOptional();
  const draftApi = useComposerDraftApiOptional();
  const input = draft?.input ?? "";
  const onChangeInput = draftApi ? draftApi.typeInput : noopComposerInput;
  const [scanHint, setScanHint] = useState(false);
  const inputRef = useRef<TextInputInstance>(null);
  const math = useMathKeyboardInsert({
    input,
    draftRevision: draft?.revision,
    setInput: onChangeInput,
    onImageOnlyPaste: onOpenMathScanner ? () => setScanHint(true) : undefined,
  });
  const { showMathPreview, mathBarOpen, toggleMathBar } = math;
  const padUnder = math.mathBarOpen ? math.padHeight : 0;
  const mathChromeHeight =
    padUnder +
    (math.mathBarOpen && liveAnswerShows(input) ? MATH_LIVE_ANSWER_HEIGHT : 0) +
    (showMathPreview ? MATH_DRAFT_PREVIEW_HEIGHT : 0) +
    (scanHint ? COMPOSER_SCAN_HINT_HEIGHT : 0) +
    (sendStatus ? COMPOSER_STATUS_LINE_HEIGHT : 0);

  // Kept while the drawer hides the composer, so opening it does not re-lay out the chat.
  useEffect(() => {
    onMathChromeHeightChange?.(mathChromeHeight, padUnder);
  }, [mathChromeHeight, onMathChromeHeightChange, padUnder]);

  const padField = useMathPadField(math.mathBarOpen, inputRef, math.insertSymbol);

  // The system keyboard dismisses on send and stays down while a reply streams.
  // The math pad is not a system keyboard, so close it the same way.
  useEffect(() => {
    if (!streaming || !math.mathBarOpen) return;
    toggleMathBar();
  }, [streaming, math.mathBarOpen, toggleMathBar]);

  // Scanner/expanded chrome belongs to the active draft, not the mounted screen.
  // Switching threads can keep ChatComposer mounted, so clear transient UI explicitly.
  useEffect(() => {
    setScanHint(false);
  }, [draft?.revision]);

  const voiceActive = voiceRecording || voiceTranscribing;
  // While the waveform takes the field's place, the row never splits.
  const rowFit = useComposerRowFit(voiceActive ? "" : input, fontScale);
  const {
    composerExpanded,
    toggleExpanded,
    inputContentWidth,
    onTextMeasure,
    field,
    textBoxHeight,
    fieldOverflows,
    showExpandControl,
    onInputLayout,
    onInputContentSizeChange,
  } = useComposerFieldLayout({
    input,
    draftRevision: draft?.revision,
    fontScale,
    buttonRowBelow: rowFit.wraps,
    onInputFrameExtraChange,
  });
  const stacked = rowFit.wraps || composerExpanded;

  const bottomPad = Math.max(insets.bottom, CHAT_COMPOSER_MIN_BOTTOM_PAD);
  const gapFadeStyle = useAnimatedStyle(() => {
    "worklet";
    // The math pad fills the home-indicator gap. A scrim there would paint
    // across the keys instead of the messages above the pill.
    const pad =
      (keyboardHeight?.value ?? 0) > 0 || composerExpanded || mathBarOpen ? 0 : bottomPad;
    // Inline the height. Calling an imported helper here runs on the UI
    // thread and aborts the app.
    const height = pad <= 0 ? 0 : pad * 2 + COMPOSER_GAP_FADE_OVERLAP;
    return {
      height,
      bottom: pad > 0 ? -pad : 0,
    };
  });

  const onToggleMathBar = useCallback(() => {
    if (streaming && !mathBarOpen) return;
    const wasOpen = mathBarOpen;
    toggleMathBar();
    if (wasOpen) {
      padField.focusForTyping();
    }
  }, [mathBarOpen, padField, streaming, toggleMathBar]);

  useMathKeyboardRequests(mathBarOpen ? noopOpen : onToggleMathBar);

  const sendAndCloseMath = useCallback(
    (text?: string) => {
      if (math.mathBarOpen) toggleMathBar();
      onSend(text);
    },
    [math.mathBarOpen, onSend, toggleMathBar],
  );

  if (!visible || liveTalkActive) return null;

  const hasSendableContent = Boolean(input.trim() || pendingAttachment);
  const attachmentDisabled = attachPicking || sendBusy || streaming;
  const parkInput = showMathPreview;
  const showEmptyCaret = math.mathBarOpen && !showMathPreview && !input.trim();
  const showMic = composerShowsMic({
    voiceAvailable: Boolean(voiceAvailable && onVoicePress && token),
    voiceRecording,
    voiceTranscribing,
    hasSendableContent,
  });
  const showSend = composerShowsSend({
    voiceRecording,
    voiceTranscribing,
    hasSendableContent,
  });
  const blockStyle = s.composerBlock;
  const expandedBlockStyle = composerExpanded
    ? [s.composerBlockExpanded, { top: insets.top + Space.xs }]
    : null;
  const containerStyle = animatedContainerStyle
    ? [blockStyle, animatedContainerStyle, expandedBlockStyle]
    : [blockStyle, expandedBlockStyle];
  const attachButton = (
    <ComposerAttachButton
      s={s}
      voiceActive={voiceActive}
      disabled={attachmentDisabled}
      picking={attachPicking}
      onPress={() => {
        if (voiceActive) {
          onCancelVoice?.();
          return;
        }
        onPickAttachment();
      }}
    />
  );
  const trailingControls = (
    <View style={s.trailingControls} onLayout={rowFit.onTrailingLayout} testID="composer-trailing-controls">
      <ComposerSendControls
        s={s}
        streaming={streaming}
        onStop={onStop}
        onSend={() => sendAndCloseMath()}
        showSend={showSend}
        sendBusy={sendBusy}
        isOffline={isOffline}
        attachBusy={attachPicking}
        showMic={showMic}
        voiceRecording={voiceRecording}
        voiceTranscribing={voiceTranscribing}
        onVoicePress={onVoicePress}
        onLiveTalkPress={onLiveTalkPress}
      />
    </View>
  );

  return (
    <Animated.View
      style={containerStyle}
      pointerEvents="box-none"
      testID="chat-composer"
    >
      <Animated.View
        pointerEvents="none"
        style={[s.bottomFade, gapFadeStyle]}
        testID="composer-bottom-fade"
      >
        <LinearGradient
          colors={composerGapFadeColors(theme.bg)}
          locations={[...COMPOSER_GAP_FADE_LOCATIONS]}
          style={StyleSheet.absoluteFill}
        />
      </Animated.View>
      <View style={[s.composerAnchor, composerExpanded && s.expandedFill]}>
        <View style={[s.composer, composerExpanded && s.expandedFill]}>
          {scanHint && onOpenMathScanner ? (
            <ComposerScanHint
              s={s}
              onOpenScanner={() => {
                setScanHint(false);
                onOpenMathScanner();
              }}
              onDismiss={() => setScanHint(false)}
            />
          ) : null}
          <View style={[s.inputStack, composerExpanded && s.expandedFill]}>
          <View style={composerExpanded && s.expandedFill}>
          <View
            testID="composer-surface"
            style={[
              s.inputWrap,
              composerExpanded && s.inputWrapExpanded,
            ]}
          >
            {pendingAttachment ? (
              <ComposerAttachmentPreview
                attachment={pendingAttachment}
                uploading={attachPicking}
                onRemove={onRemoveAttachment}
              />
            ) : null}
            {showExpandControl ? (
              <ComposerExpandControl
                s={s}
                expanded={composerExpanded}
                onPress={() => {
                  toggleExpanded();
                  padField.focusSoon();
                }}
              />
            ) : null}
            {/* One row while the draft fits: + just before the caret, the field, then mic and
                live talk (or send). Once it wraps, the text runs end to end over the buttons. */}
            <View
              testID="composer-input-row"
              style={[s.inputRowMain, composerExpanded && s.inputRowMainExpanded]}
              onLayout={rowFit.onRowLayout}
            >
              {stacked ? null : attachButton}
              {voiceRecording || voiceTranscribing ? (
                <VoiceComposerWaveform
                  recording={voiceRecording}
                  transcribing={voiceTranscribing}
                  meterLevel={voiceMeterLevel}
                />
              ) : (
                <Pressable
                  style={[
                    s.inputField,
                    // Keeps one line on the field's midline. Extra lines grow above the caret.
                    { paddingBottom: field.slack / 2 },
                    stacked && s.inputFieldStacked,
                    composerExpanded && s.inputFieldExpanded,
                  ]}
                  testID="chat-composer-field"
                  accessible={false} // a tap area; screen readers reach the text field inside
                  onPress={() => {
                    if (math.mathBarOpen || showMathPreview) return;
                    if (math.resumeMathOnFocus) math.openMathBar();
                  }}
                >
                  {showMathPreview ? (
                    <MathDraftPreview
                      input={input}
                      caret={math.selection.start}
                      onMoveCaret={(pos) => {
                        if (math.mathBarOpen) {
                          math.moveCaret(pos);
                          return;
                        }
                        const before = caretBeforeExpression(input);
                        const after = caretAfterExpression(input);
                        if (pos <= before) math.moveCaret(0);
                        else if (pos >= after) math.moveCaret(input.length);
                        else math.moveCaret(pos);
                      }}
                    />
                  ) : null}
                  <ComposerTextMeasure
                    text={input}
                    width={inputContentWidth}
                    onMeasure={onTextMeasure}
                  />
                  <TextInput
                    ref={inputRef}
                    testID="chat-composer-input"
                    style={[
                      s.input,
                      composerExpanded
                        ? s.inputExpanded
                        : {
                            height: textBoxHeight,
                            minHeight: textBoxHeight,
                            maxHeight: field.max,
                            paddingTop: 0,
                            paddingBottom: 0,
                            textAlignVertical: "top" as const,
                          },
                      parkInput ? s.inputParked : null,
                    ]}
                    accessibilityLabel={prompt}
                    maxFontSizeMultiplier={DYNAMIC_TYPE_MAX}
                    value={input}
                    // Messaging traits while the system keyboard is up. The math
                    // pad dismisses that keyboard before it takes the field, so
                    // correction does not flip mid-word inside one native session.
                    {...composerNativeInputTraits(math.mathBarOpen || showMathPreview)}
                    onChangeText={math.onChangeText}
                    onLayout={onInputLayout}
                    onContentSizeChange={onInputContentSizeChange}
                    scrollEnabled={fieldOverflows && !composerExpanded}
                    onSelectionChange={math.onSelectionChange}
                    selection={
                      showMathPreview
                        ? (math.forcedSelection ?? math.selection)
                        : undefined
                    }
                    caretHidden={showMathPreview || math.mathBarOpen}
                    pointerEvents={parkInput || math.mathBarOpen ? "none" : "auto"}
                    showSoftInputOnFocus={!math.resumeMathOnFocus}
                    onFocus={() => {
                      onCloseAttachSheet();
                      math.onComposerFocus();
                    }}
                    multiline
                    returnKeyType="default"
                  />
                  {input || showMathPreview ? null : <ComposerPlaceholder bottom={field.slack / 2} />}
                  {showEmptyCaret ? (
                    <View style={s.emptyCaret} pointerEvents="none">
                      <MathComposerCaret testID="math-composer-caret" />
                    </View>
                  ) : null}
                </Pressable>
              )}
              {stacked ? null : trailingControls}
            </View>
            {math.mathBarOpen && liveAnswerShows(input) ? <MathLiveAnswer input={input} /> : null}
            {stacked ? (
              <View style={s.controlsRow} testID="composer-controls-row">
                {attachButton}
                {trailingControls}
              </View>
            ) : null}
            {sendStatus ? (
              <Text
                style={s.sendStatus}
                testID="composer-send-status"
                accessibilityRole="text"
                accessibilityLiveRegion="polite"
              >
                {sendStatus}
              </Text>
            ) : null}
          </View>
          </View>
          {mathBarOpen && !composerExpanded ? (
            <LinearGradient
              pointerEvents="none"
              colors={bottomChromeFadeColors(theme) as [string, string, ...string[]]}
              locations={[...BOTTOM_CHROME_FADE_LOCATIONS]}
              style={[s.keyboardGapFade, { bottom: math.padHeight }]}
              testID="composer-scroll-fade"
            />
          ) : null}
          {math.mathBarOpen ? (
            <MathKeyboardBar
              open
              height={math.padHeight}
              onToggle={onToggleMathBar}
              onInsert={padField.insert}
              onCaret={math.stepCaret}
              onAsk={sendAndCloseMath}
              onStop={onStop}
              streaming={streaming}
              onBackspace={math.backspace}
              onPaste={() => pasteClipboardText(math.pasteText)}
              group={math.mathGroup}
              onGroupChange={math.setMathGroup}
            />
          ) : null}
        </View>
        </View>
      </View>
    </Animated.View>
  );
});
