import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
  type ViewStyle,
} from "react-native";
import Animated, {
  useAnimatedKeyboard,
  useAnimatedStyle,
  type AnimatedStyle,
} from "react-native-reanimated";
import * as Clipboard from "expo-clipboard";
import { LinearGradient } from "expo-linear-gradient";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Icon } from "@/ui/icons/Icon";
import { useTranslation } from "react-i18next";

import { LiveTalkButton } from "@/features/speech/components/LiveTalkButton";
import { LiveTalkComposerControls } from "@/features/speech/components/LiveTalkComposerControls";
import { VoiceComposerWaveform } from "@/features/speech/components/VoiceComposerWaveform";
import { VoiceMicButton } from "@/features/speech/components/VoiceMicButton";
import {
  MathDraftPreview,
  MATH_DRAFT_PREVIEW_HEIGHT,
} from "@/components/chat/MathDraftPreview";
import { MathComposerCaret } from "@/components/chat/MathComposerCaret";
import { MathKeyboardBar } from "@/components/chat/MathKeyboardBar";
import { ComposerAttachmentPreview } from "@/features/attachments/components/ComposerAttachmentPreview";
import {
  useComposerDraftApiOptional,
  useComposerDraftValueOptional,
} from "@/contexts/ComposerDraftContext";
import { useAuthToken } from "@/contexts/AuthContext";
import { useMathKeyboardInsert } from "@/hooks/useMathKeyboardInsert";
import type { PendingAttachment } from "@/features/attachments/model/attachments";
import {
  CHAT_COMPOSER_MIN_BOTTOM_PAD,
  COMPOSER_GAP_FADE_OVERLAP,
  COMPOSER_INPUT_LINE_HEIGHT,
  COMPOSER_INPUT_MAX_HEIGHT,
  COMPOSER_CONTROL_SIZE,
  COMPOSER_INPUT_MIN_HEIGHT,
  composerInputFrameHeight,
  composerInputMetrics,
  composerInputTextBoxHeight,
  retainedComposerContentHeight,
  composerNativeInputTraits,
  composerShowsMic,
  composerShowsSend,
} from "@/lib/chat/composerLogic";
import { liveTalkShowsSideChrome } from "@/features/speech/model/liveTalkLogic";
import { textLooksLikeMath } from "@/lib/math/composerIntent";
import { caretAfterExpression, caretBeforeExpression } from "@/lib/math/draftSlots";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme, withAlpha } from "@/lib/theme";
import { DYNAMIC_TYPE_MAX, Type, Weight } from "@/lib/type";
import { IconSize } from "@/ui/icons/sizes";

function noopComposerInput(_text: string) {}

const GAP_FADE_LOCATIONS = [0, 1] as const;

/** Washed out at both ends. A clear stop left a sharp line directly under the pill. */
function gapFadeColors(bg: string): [string, string] {
  return [withAlpha(bg, 0.92), bg];
}

// 36 pt row + 4 pt card padding above and below + 6 pt shell air above and below.
export const COMPOSER_HEIGHT = 56;
// Attachment extras mirror the rendered preview sizes instead of under-reserving the thread.
export const COMPOSER_IMAGE_PREVIEW_EXTRA = 120;
export const COMPOSER_FILE_PREVIEW_EXTRA = 56;
const MATH_KEYBOARD_CHIP_HEIGHT = 44;
/** Space above the floating keypad so message action icons are not flush with it. */
const MATH_KEYBOARD_CHIP_GAP = Space.sm;
const COMPOSER_STATUS_LINE_HEIGHT = 18;

export function composerAttachmentExtra(attachment: PendingAttachment | null): number {
  if (!attachment) return 0;
  return attachment.kind === "image" ? COMPOSER_IMAGE_PREVIEW_EXTRA : COMPOSER_FILE_PREVIEW_EXTRA;
}

type Props = {
  visible: boolean;
  bottom?: number;
  paddingBottom?: number;
  animatedContainerStyle?: AnimatedStyle<ViewStyle>;
  /** Tests pass these; production reads ComposerDraftContext. */
  input?: string;
  onChangeInput?: (text: string) => void;
  streaming: boolean;
  attachBusy: boolean;
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
  voiceMeterLevel?: number;
  onVoicePress?: () => void;
  /** Drops the open mic take, including a transcription already in flight. */
  onCancelVoice?: () => void;
  onLiveTalkPress?: () => void;
  /** Mic mute + close beside the real composer while live talk is open. */
  liveTalkChrome?: {
    muted: boolean;
    onClose: () => void;
    onMutePress: () => void;
    onYield: () => void;
  } | null;
  /** When true, parent owns absolute bottom positioning (e.g. math keypad). */
  docked?: boolean;
  onOpenMathScanner?: () => void;
  onMathChromeHeightChange?: (height: number) => void;
  /** Extra field height past one line, so the thread moves up with the pill. */
  onInputFrameExtraChange?: (extra: number) => void;
  /** Recent chat already has math — offer the math keyboard even with an empty composer. */
  mathContext?: boolean;
};

export const ChatComposer = memo(function ChatComposer({
  visible,
  bottom,
  paddingBottom,
  animatedContainerStyle,
  input: inputProp,
  onChangeInput: onChangeInputProp,
  streaming,
  attachBusy,
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
  voiceMeterLevel = 0.12,
  onVoicePress,
  onCancelVoice,
  onLiveTalkPress,
  liveTalkChrome = null,
  docked = false,
  onOpenMathScanner,
  onMathChromeHeightChange,
  onInputFrameExtraChange,
  mathContext = false,
}: Props) {
  const { t } = useTranslation();
  const token = useAuthToken();
  const insets = useSafeAreaInsets();
  // Native text scales the field's line box with the system text size.
  const { fontScale } = useWindowDimensions();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const draft = useComposerDraftValueOptional();
  const draftApi = useComposerDraftApiOptional();
  const input = inputProp ?? draft?.input ?? "";
  const onChangeInput =
    onChangeInputProp ??
    (draftApi ? (text: string) => draftApi.setInput(text) : noopComposerInput);
  const [scanHint, setScanHint] = useState(false);
  const [inputHeight, setInputHeight] = useState<number>(COMPOSER_INPUT_MIN_HEIGHT);
  const [inputContentWidth, setInputContentWidth] = useState(0);
  const [composerExpanded, setComposerExpanded] = useState(false);
  const inputRef = useRef<TextInput>(null);
  const measuredContent = useRef<{ revision: number; height: number } | null>(null);
  const math = useMathKeyboardInsert({
    input,
    draftRevision: draft?.revision,
    setInput: onChangeInput,
    onImageOnlyPaste: onOpenMathScanner ? () => setScanHint(true) : undefined,
  });
  const showMathPreview = math.showMathPreview;
  const mathBarOpen = math.mathBarOpen;
  const toggleMathBar = math.toggleMathBar;
  const showMathChip =
    !mathBarOpen && (mathContext || textLooksLikeMath(input));
  const mathChromeHeight =
    (math.mathBarOpen
      ? math.padHeight
      : showMathChip
        ? MATH_KEYBOARD_CHIP_HEIGHT + MATH_KEYBOARD_CHIP_GAP
        : 0) +
    (showMathPreview ? MATH_DRAFT_PREVIEW_HEIGHT : 0) +
    (scanHint ? 40 : 0) +
    (sendStatus ? COMPOSER_STATUS_LINE_HEIGHT : 0);

  useEffect(() => {
    onMathChromeHeightChange?.(visible ? mathChromeHeight : 0);
  }, [mathChromeHeight, onMathChromeHeightChange, visible]);

  useEffect(() => {
    if (!math.mathBarOpen) return;
    const id = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(id);
  }, [math.mathBarOpen]);

  // Scanner/expanded chrome belongs to the active draft, not the mounted screen.
  // Switching threads can keep ChatComposer mounted, so clear transient UI explicitly.
  useEffect(() => {
    setScanHint(false);
    setComposerExpanded(false);
  }, [draft?.revision]);

  useEffect(() => {
    // iOS can retain the last multiline content size after a controlled
    // TextInput is cleared. Pin the empty draft back to the single-line
    // height so a sent long message cannot leave a tall blank composer.
    // Within one draft, keep the last wrap height: a keystroke changes the
    // string without a new content-size event. A thread switch (revision)
    // drops that sample so the next draft does not inherit it.
    const revision = draft?.revision ?? 0;
    if (!input) {
      measuredContent.current = null;
      setInputHeight(COMPOSER_INPUT_MIN_HEIGHT);
      setComposerExpanded(false);
      return;
    }
    const measured = retainedComposerContentHeight(
      measuredContent.current,
      revision,
      input,
    );
    const frame = composerInputFrameHeight(input, measured, inputContentWidth, fontScale);
    setInputHeight(frame.height);
  }, [draft?.revision, fontScale, input, inputContentWidth]);

  // Only hard returns move the thread. A soft wrap grows the field in place;
  // pushing list padding here is what yanks the chat up on every line.
  // Measured from the 44 pt field COMPOSER_HEIGHT assumes, so a taller line
  // at a large text size moves the thread too.
  const returnFrame = composerInputFrameHeight(input, 0, 0, fontScale);
  const inputFrameExtra = composerExpanded
    ? 0
    : Math.max(0, returnFrame.height - COMPOSER_INPUT_MIN_HEIGHT);
  useEffect(() => {
    onInputFrameExtraChange?.(visible ? inputFrameExtra : 0);
  }, [inputFrameExtra, onInputFrameExtraChange, visible]);

  const bottomPad = Math.max(insets.bottom, CHAT_COMPOSER_MIN_BOTTOM_PAD);
  const keyboard = useAnimatedKeyboard();
  const gapFadeStyle = useAnimatedStyle(() => {
    "worklet";
    const pad = keyboard.height.value > 0 || composerExpanded ? 0 : bottomPad;
    // Inline the height. Calling composerGapFadeHeight here runs on the UI
    // thread and aborts the app.
    const height = pad <= 0 ? 0 : pad * 2 + COMPOSER_GAP_FADE_OVERLAP;
    return {
      height,
      bottom: pad > 0 ? -pad : 0,
    };
  });

  const onToggleMathBar = useCallback(() => {
    const wasOpen = mathBarOpen;
    toggleMathBar();
    if (wasOpen) {
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [mathBarOpen, toggleMathBar]);

  if (!visible) return null;

  const hasSendableContent = Boolean(input.trim() || pendingAttachment);
  const attachmentDisabled = attachBusy || attachPicking || sendBusy || streaming;
  const showLiveTalkSideChrome =
    Boolean(liveTalkChrome) && liveTalkShowsSideChrome(input);
  const parkInput = showMathPreview;
  const showEmptyCaret = math.mathBarOpen && !showMathPreview && !input.trim();
  const showMic = composerShowsMic({
    voiceAvailable: Boolean(voiceAvailable && onVoicePress && token && !liveTalkChrome),
    voiceRecording,
    voiceTranscribing,
    hasSendableContent,
  });
  const voiceActive = voiceRecording || voiceTranscribing;
  const showSend = composerShowsSend({
    voiceRecording,
    voiceTranscribing,
    hasSendableContent,
  });
  const draftRevision = draft?.revision ?? 0;
  const measuredNow = input
    ? retainedComposerContentHeight(measuredContent.current, draftRevision, input)
    : 0;
  const field = composerInputMetrics(fontScale);
  const frameNow = composerInputFrameHeight(
    input,
    Math.max(measuredNow, inputHeight),
    inputContentWidth,
    fontScale,
  );
  // Same render as the keystroke. Waiting for the effect leaves one frame
  // clipped at the end of the line.
  const fieldHeight = input ? frameNow.height : field.min;
  // Text box matches the lines. Centering slack stays on the wrapper so the
  // caret remains on the last line, beside the buttons.
  const textBoxHeight = composerInputTextBoxHeight(fieldHeight, fontScale);
  const fieldOverflows = Boolean(input) && frameNow.overflows;
  const singleLineComposer = !composerExpanded && fieldHeight <= field.min;

  const blockStyle = docked ? s.composerDocked : s.composerBlock;
  const expandedBlockStyle = composerExpanded
    ? [s.composerBlockExpanded, { top: insets.top + Space.xs }]
    : null;
  const containerStyle = animatedContainerStyle
    ? [blockStyle, animatedContainerStyle, expandedBlockStyle]
    : [blockStyle, { bottom, paddingBottom }, expandedBlockStyle];
  const showExpandControl = fieldOverflows || composerExpanded;
  // The composer view is only as tall as the field. A target drawn above that
  // box never receives taps, so while the math pad is open the view itself
  // stretches to the top of the screen and the dismiss target fills that space.
  const mathDismissCoversScreen = math.mathBarOpen && !composerExpanded && !docked;

  return (
    <Animated.View
      style={[containerStyle, mathDismissCoversScreen && s.mathHitHost]}
      pointerEvents="box-none"
      testID="chat-composer"
    >
      <Animated.View
        pointerEvents="none"
        style={[s.bottomFade, gapFadeStyle]}
        testID="composer-bottom-fade"
      >
        <LinearGradient
          colors={gapFadeColors(theme.bg)}
          locations={[...GAP_FADE_LOCATIONS]}
          style={StyleSheet.absoluteFill}
        />
      </Animated.View>
      {mathDismissCoversScreen ? (
        <Pressable
          style={s.outsideDismiss}
          onPress={() => {
            math.dismissMathBar();
            inputRef.current?.blur();
          }}
          accessibilityRole="button"
          accessibilityLabel={t("common.close")}
          testID="math-keyboard-dismiss"
        />
      ) : null}
      <View style={[s.composerAnchor, composerExpanded && s.expandedFill]}>
        <View style={[s.composer, composerExpanded && s.expandedFill]}>
          {scanHint && onOpenMathScanner ? (
            <View style={s.scanHint}>
              <Text style={s.scanHintText}>{t("chat.math_paste_scan_hint")}</Text>
              <Pressable
                onPress={() => {
                  setScanHint(false);
                  onOpenMathScanner();
                }}
                accessibilityRole="button"
                accessibilityLabel={t("chat.math_paste_scan_cta")}
              >
                <Text style={s.scanHintCta}>{t("chat.math_paste_scan_cta")}</Text>
              </Pressable>
              <Pressable onPress={() => setScanHint(false)} accessibilityRole="button" accessibilityLabel={t("common.cancel")}>
                <Icon name="close" size={IconSize.xs} color={theme.textSecondary} />
              </Pressable>
            </View>
          ) : null}
          <View style={[s.inputStack, composerExpanded && s.expandedFill]}>
            {showMathChip ? (
              <Pressable
                onPress={onToggleMathBar}
                style={({ pressed }) => [s.chip, pressed && s.chipPressed]}
                accessibilityRole="button"
                accessibilityLabel={t("chat.math_keyboard_show")}
                testID="math-keyboard-toggle"
              >
                <Icon name="calculator" size={IconSize.sm} color={theme.primary} />
              </Pressable>
            ) : null}
          <View
            style={[
              showLiveTalkSideChrome ? s.liveTalkRow : null,
              composerExpanded && s.expandedFill,
            ]}
          >
          <View
            testID="composer-surface"
            style={[
              s.inputWrap,
              showLiveTalkSideChrome ? s.inputWrapFlex : null,
              composerExpanded && s.inputWrapExpanded,
            ]}
          >
            {pendingAttachment ? (
              <ComposerAttachmentPreview
                attachment={pendingAttachment}
                uploading={attachBusy}
                onRemove={onRemoveAttachment}
              />
            ) : null}
            {showExpandControl ? (
              <View style={s.expandControlRow}>
                <Pressable
                  style={s.expandControl}
                  onPress={() => {
                    setComposerExpanded((expanded) => !expanded);
                    requestAnimationFrame(() => inputRef.current?.focus());
                  }}
                  accessibilityRole="button"
                  accessibilityLabel={t(composerExpanded ? "rich.collapse" : "rich.expand")}
                  accessibilityState={{ expanded: composerExpanded }}
                  testID="composer-expand"
                >
                  <Icon
                    name={composerExpanded ? "collapse" : "expand"}
                    size={IconSize.sm}
                    color={theme.textSecondary}
                  />
                </Pressable>
              </View>
            ) : null}
            <View
              testID="composer-input-row"
              style={[
                s.inputRowMain,
                singleLineComposer && s.inputRowMainSingleLine,
                composerExpanded && s.inputRowMainExpanded,
              ]}
            >
              <Pressable
                testID="composer-attachment-button"
                style={[s.attachBtn, !voiceActive && attachmentDisabled && s.controlDisabled]}
                onPress={() => {
                  if (voiceActive) {
                    onCancelVoice?.();
                    return;
                  }
                  liveTalkChrome?.onYield();
                  onPickAttachment();
                }}
                disabled={!voiceActive && attachmentDisabled}
                hitSlop={{ top: 14, bottom: 14, left: 14, right: 14 }}
                accessibilityRole="button"
                accessibilityLabel={t(voiceActive ? "chat.voice_cancel_a11y" : "chat.attach_a11y")}
                accessibilityState={{
                  disabled: !voiceActive && attachmentDisabled,
                  busy: !voiceActive && attachPicking,
                }}
              >
                {voiceActive ? (
                  <Icon
                    name="close"
                    size={IconSize.md}
                    color={theme.text}
                    testID="composer-voice-cancel-icon"
                  />
                ) : attachPicking ? (
                  <ActivityIndicator size="small" color={theme.text} />
                ) : (
                  <Icon
                    name="plus"
                    size={IconSize.md}
                    color={theme.text}
                    testID="composer-attachment-add-icon"
                  />
                )}
              </Pressable>
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
                    // Keeps one line on the button midline. Extra lines grow above the caret.
                    { paddingBottom: field.slack / 2 },
                    composerExpanded && s.inputFieldExpanded,
                  ]}
                  testID="chat-composer-field"
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
                    placeholder={showMathPreview ? "" : t("chat.placeholder")}
                    placeholderTextColor={theme.textDisabled}
                    accessibilityLabel={t("chat.placeholder")}
                    maxFontSizeMultiplier={DYNAMIC_TYPE_MAX}
                    value={input}
                    // Messaging traits while the system keyboard is up. The math
                    // pad dismisses that keyboard before it takes the field, so
                    // correction does not flip mid-word inside one native session.
                    {...composerNativeInputTraits(math.mathBarOpen || showMathPreview)}
                    onChangeText={math.onChangeText}
                    onLayout={(event) => {
                      const next = Math.round(event.nativeEvent.layout.width);
                      if (next <= 0) return;
                      setInputContentWidth((current) => (current === next ? current : next));
                    }}
                    onContentSizeChange={(event) => {
                      const measured = Math.ceil(event.nativeEvent.contentSize.height);
                      measuredContent.current = {
                        revision: draft?.revision ?? 0,
                        height: measured,
                      };
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
                    }}
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
                      liveTalkChrome?.onYield();
                      math.onComposerFocus();
                    }}
                    multiline
                    returnKeyType="default"
                  />
                  {showEmptyCaret ? (
                    <View style={s.emptyCaret} pointerEvents="none">
                      <MathComposerCaret testID="math-composer-caret" />
                    </View>
                  ) : null}
                </Pressable>
              )}
              <View style={s.sendBtnSlot}>
                {streaming ? (
                  <Pressable
                    style={s.sendBtn}
                    onPress={onStop}
                    hitSlop={6}
                    accessibilityRole="button"
                    accessibilityLabel={t("chat.stop_a11y")}
                  >
                    <Icon name="stop" size={IconSize.xxs} color={theme.onPrimary} />
                  </Pressable>
                ) : (
                  <>
                    {showMic && onVoicePress ? (
                      <VoiceMicButton
                        recording={voiceRecording}
                        transcribing={voiceTranscribing}
                        disabled={attachBusy || attachPicking || sendBusy || isOffline}
                        onPress={onVoicePress}
                      />
                    ) : null}
                    {onLiveTalkPress &&
                    !liveTalkChrome &&
                    !voiceRecording &&
                    !voiceTranscribing &&
                    !showSend &&
                    !sendBusy ? (
                      <LiveTalkButton
                        disabled={attachBusy || attachPicking || isOffline}
                        onPress={onLiveTalkPress}
                      />
                    ) : null}
                    {showSend || sendBusy ? (
                      <Pressable
                        style={[
                          s.sendBtn,
                          (isOffline || sendBusy) && s.sendBtnDisabled,
                        ]}
                        onPress={() => onSend()}
                        disabled={isOffline || sendBusy}
                        hitSlop={6}
                        accessibilityRole="button"
                        accessibilityLabel={
                          sendBusy ? t("chat.sending") : t("chat.send_a11y")
                        }
                        accessibilityHint={isOffline ? t("chat.offline_body") : undefined}
                        accessibilityState={{
                          disabled: isOffline || sendBusy,
                          busy: sendBusy,
                        }}
                      >
                        {sendBusy ? (
                          <ActivityIndicator size="small" color={theme.textTertiary} />
                        ) : (
                          <Icon
                            name="arrow-up"
                            size={IconSize.sm}
                            color={isOffline ? theme.textTertiary : theme.onPrimary}
                          />
                        )}
                      </Pressable>
                    ) : null}
                  </>
                )}
              </View>
            </View>
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
          {liveTalkChrome && showLiveTalkSideChrome ? (
            <LiveTalkComposerControls
              muted={liveTalkChrome.muted}
              onMutePress={liveTalkChrome.onMutePress}
              onClose={liveTalkChrome.onClose}
            />
          ) : null}
          </View>
          {math.mathBarOpen ? (
            <MathKeyboardBar
              open
              height={math.padHeight}
              onToggle={onToggleMathBar}
              onInsert={math.insertSymbol}
              onAsk={onSend}
              onStop={onStop}
              streaming={streaming}
              onBackspace={math.backspace}
              onPaste={() => {
                void Clipboard.getStringAsync().then((text) => {
                  if (text) void math.pasteText(text);
                });
              }}
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

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    composerBlock: {
      position: "absolute",
      left: 0,
      right: 0,
      zIndex: 110,
      overflow: "visible",
      backgroundColor: "transparent",
      paddingHorizontal: Space.md,
      paddingTop: Space.xxs,
    },
    mathHitHost: { top: 0 },
    outsideDismiss: { flex: 1, marginHorizontal: -Space.sm },
    composerDocked: {
      overflow: "visible",
      backgroundColor: "transparent",
      paddingHorizontal: Space.md,
      paddingTop: Space.xxs,
    },
    composerBlockExpanded: {
      zIndex: 200,
      backgroundColor: theme.bg,
    },
    expandedFill: { flex: 1, minHeight: 0 },
    bottomFade: {
      position: "absolute",
      left: -Space.md,
      right: -Space.md,
      zIndex: 0,
    },
    composerAnchor: { position: "relative", overflow: "visible", zIndex: 1 },
    composer: { paddingVertical: 6, overflow: "visible" },
    inputStack: { position: "relative", overflow: "visible" },
    liveTalkRow: {
      flexDirection: "row",
      alignItems: "flex-end",
      gap: Space.xs,
    },
    inputWrap: {
      // Attachments and the input row live inside the same rounded card.
      backgroundColor: theme.control,
      borderRadius: Radius.sheet,
      paddingHorizontal: Space.md,
      paddingTop: Space.xxs,
      paddingBottom: Space.xxs,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.composerBorder,
    },
    inputWrapFlex: { flex: 1, minWidth: 0 },
    inputWrapExpanded: { flex: 1, minHeight: 0 },
    sendStatus: {
      marginTop: Space.xxs,
      marginLeft: 40,
      ...Type.meta,
      color: theme.textSecondary,
    },
    inputRowMain: { flexDirection: "row", alignItems: "flex-end", gap: Space.xs },
    inputRowMainSingleLine: { alignItems: "center" },
    inputRowMainExpanded: { flex: 1, minHeight: 0 },
    inputField: {
      flex: 1,
      justifyContent: "flex-end",
      minHeight: COMPOSER_INPUT_MIN_HEIGHT,
      position: "relative",
    },
    inputFieldExpanded: { justifyContent: "flex-start", minHeight: 0, paddingBottom: 0 },
    expandControlRow: {
      minHeight: Space.minTouch,
      flexDirection: "row",
      justifyContent: "flex-end",
      alignItems: "center",
    },
    expandControl: {
      width: Space.minTouch,
      height: Space.minTouch,
      borderRadius: Space.minTouch / 2,
      alignItems: "center",
      justifyContent: "center",
    },
    emptyCaret: {
      position: "absolute",
      left: 0,
      top: 2,
      bottom: 2,
      justifyContent: "center",
      zIndex: 2,
    },
    attachBtn: {
      width: COMPOSER_CONTROL_SIZE,
      height: COMPOSER_CONTROL_SIZE,
      borderRadius: COMPOSER_CONTROL_SIZE / 2,
      // Keep the + as quiet chrome inside the shared composer surface.
      borderWidth: 0,
      borderColor: "transparent",
      backgroundColor: "transparent",
      alignItems: "center",
      justifyContent: "center",
      marginBottom: 0,
    },
    controlDisabled: { opacity: 0.55 },
    chip: {
      position: "absolute",
      left: 0,
      top: -(MATH_KEYBOARD_CHIP_HEIGHT + Space.xxs),
      zIndex: 1,
      minWidth: Space.minTouch,
      minHeight: Space.minTouch,
      height: Space.minTouch,
      paddingHorizontal: 10,
      borderRadius: Radius.xl,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: "transparent",
    },
    chipPressed: { opacity: 0.55 },
    input: {
      flex: 1,
      ...Type.body,
      color: theme.text,
      // Fixed line box. A padded field makes iOS draw the caret a line too high.
      lineHeight: COMPOSER_INPUT_LINE_HEIGHT,
      maxHeight: COMPOSER_INPUT_MAX_HEIGHT,
      paddingVertical: 0,
      minHeight: COMPOSER_INPUT_LINE_HEIGHT,
    },
    inputExpanded: {
      height: undefined,
      maxHeight: undefined,
      minHeight: 0,
      textAlignVertical: "top",
    },
    inputParked: {
      position: "absolute",
      width: 1,
      height: 1,
      opacity: 0,
      overflow: "hidden",
      flex: 0,
    },
    sendBtn: {
      width: COMPOSER_CONTROL_SIZE,
      height: COMPOSER_CONTROL_SIZE,
      borderRadius: Radius.full,
      backgroundColor: theme.primary,
      alignItems: "center",
      justifyContent: "center",
    },
    sendBtnSlot: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "flex-end",
      gap: Space.xxs,
      minHeight: COMPOSER_CONTROL_SIZE,
    },
    sendBtnDisabled: { backgroundColor: theme.border },
    scanHint: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      marginBottom: 6,
      paddingHorizontal: 10,
      paddingVertical: Space.xs,
      borderRadius: Radius.sm,
      backgroundColor: theme.primaryLight,
    },
    scanHintText: { flex: 1, ...Type.compact, color: theme.text },
    scanHintCta: { ...Type.compact, ...Weight.bold, color: theme.primary },
  });
}
