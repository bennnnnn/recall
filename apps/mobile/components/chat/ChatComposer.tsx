import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
  type ViewStyle,
} from "react-native";
import Animated, { type AnimatedStyle } from "react-native-reanimated";
import * as Clipboard from "expo-clipboard";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Icon } from "@/components/Icon";
import { useTranslation } from "react-i18next";

import { LiveTalkButton } from "@/components/chat/LiveTalkButton";
import { LiveTalkComposerControls } from "@/components/chat/LiveTalkComposerControls";
import { VoiceComposerWaveform } from "@/components/chat/VoiceComposerWaveform";
import { VoiceMicButton } from "@/components/chat/VoiceMicButton";
import {
  MathDraftPreview,
  MATH_DRAFT_PREVIEW_HEIGHT,
} from "@/components/chat/MathDraftPreview";
import { MathComposerCaret } from "@/components/chat/MathComposerCaret";
import { MathKeyboardBar } from "@/components/chat/MathKeyboardBar";
import { ComposerAttachmentPreview } from "@/components/ComposerAttachmentPreview";
import {
  useComposerDraftApiOptional,
  useComposerDraftValueOptional,
} from "@/contexts/ComposerDraftContext";
import { useAuthToken } from "@/contexts/AuthContext";
import { useMathKeyboardInsert } from "@/hooks/useMathKeyboardInsert";
import type { PendingAttachment } from "@/lib/attachments";
import { composerShowsMic, composerShowsSend } from "@/lib/chat/composerLogic";
import { liveTalkShowsSideChrome } from "@/lib/speech/liveTalkLogic";
import { estimateTokens, shouldShowDraftTokenHint } from "@/lib/estimateTokens";
import { textLooksLikeMath } from "@/lib/math/composerIntent";
import { caretAfterExpression, caretBeforeExpression } from "@/lib/math/draftSlots";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { IconSize } from "@/lib/icons";

function noopComposerInput(_text: string) {}

export const COMPOSER_HEIGHT = 88;
export const COMPOSER_IMAGE_PREVIEW_EXTRA = 84;
export const COMPOSER_FILE_PREVIEW_EXTRA = 44;
const MATH_KEYBOARD_CHIP_HEIGHT = 44;
const COMPOSER_INPUT_MIN_HEIGHT = 25;
const COMPOSER_INPUT_MAX_HEIGHT = COMPOSER_INPUT_MIN_HEIGHT * 6;
/** Space above the floating keypad so message action icons are not flush with it. */
const MATH_KEYBOARD_CHIP_GAP = Space.sm;
export const COMPOSER_TOKEN_HINT_HEIGHT = 18;

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
  onLiveTalkPress,
  liveTalkChrome = null,
  docked = false,
  onOpenMathScanner,
  onMathChromeHeightChange,
  mathContext = false,
}: Props) {
  const { t } = useTranslation();
  const token = useAuthToken();
  const insets = useSafeAreaInsets();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const draft = useComposerDraftValueOptional();
  const draftApi = useComposerDraftApiOptional();
  const input = inputProp ?? draft?.input ?? "";
  const onChangeInput =
    onChangeInputProp ??
    (draftApi ? (text: string) => draftApi.setInput(text) : noopComposerInput);
  const [scanHint, setScanHint] = useState(false);
  const [inputHeight, setInputHeight] = useState(COMPOSER_INPUT_MIN_HEIGHT);
  const [inputAtLimit, setInputAtLimit] = useState(false);
  const [composerExpanded, setComposerExpanded] = useState(false);
  const inputRef = useRef<TextInput>(null);
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
  const draftTokens = estimateTokens(input);
  const showTokenHint = shouldShowDraftTokenHint(draftTokens);
  const mathChromeHeight =
    (math.mathBarOpen
      ? math.padHeight
      : showMathChip
        ? MATH_KEYBOARD_CHIP_HEIGHT + MATH_KEYBOARD_CHIP_GAP
        : 0) +
    (showMathPreview ? MATH_DRAFT_PREVIEW_HEIGHT : 0) +
    (scanHint ? 40 : 0) +
    (showTokenHint ? COMPOSER_TOKEN_HINT_HEIGHT : 0);

  useEffect(() => {
    onMathChromeHeightChange?.(visible ? mathChromeHeight : 0);
  }, [mathChromeHeight, onMathChromeHeightChange, visible]);

  useEffect(() => {
    if (!math.mathBarOpen) return;
    const id = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(id);
  }, [math.mathBarOpen]);

  useEffect(() => {
    // iOS can retain the last multiline content size after a controlled
    // TextInput is cleared. Pin the empty draft back to the single-line
    // height so a sent long message cannot leave a tall blank composer.
    if (!input) {
      setInputHeight(COMPOSER_INPUT_MIN_HEIGHT);
      setInputAtLimit(false);
      setComposerExpanded(false);
    }
  }, [input]);

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
  const showSend = composerShowsSend({
    voiceRecording,
    voiceTranscribing,
    hasSendableContent,
  });

  const blockStyle = docked ? s.composerDocked : s.composerBlock;
  const expandedBlockStyle = composerExpanded
    ? [s.composerBlockExpanded, { top: insets.top + Space.xs }]
    : null;
  const containerStyle = animatedContainerStyle
    ? [blockStyle, animatedContainerStyle, expandedBlockStyle]
    : [blockStyle, { bottom, paddingBottom }, expandedBlockStyle];
  const showExpandControl = inputAtLimit || composerExpanded;

  return (
    <Animated.View style={containerStyle} testID="chat-composer">
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
                <Icon name="close" size={16} color={theme.textSecondary} />
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
                <Icon name="keypad-outline" size={18} color={theme.primary} />
              </Pressable>
            ) : null}
          <View
            style={[
              showLiveTalkSideChrome ? s.liveTalkRow : null,
              composerExpanded && s.expandedFill,
            ]}
          >
          <View
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
                    name={composerExpanded ? "contract-outline" : "expand-outline"}
                    size={IconSize.sm}
                    color={theme.textSecondary}
                  />
                </Pressable>
              </View>
            ) : null}
            <View style={[s.inputRowMain, composerExpanded && s.inputRowMainExpanded]}>
              <Pressable
                style={[s.attachBtn, attachmentDisabled && s.controlDisabled]}
                onPress={() => {
                  liveTalkChrome?.onYield();
                  onPickAttachment();
                }}
                disabled={attachmentDisabled}
                hitSlop={{ top: 14, bottom: 14, left: 14, right: 14 }}
                accessibilityRole="button"
                accessibilityLabel={t("chat.attach_a11y")}
                accessibilityState={{
                  disabled: attachmentDisabled,
                  busy: attachPicking,
                }}
              >
                {attachPicking ? (
                  <ActivityIndicator size="small" color={theme.primary} />
                ) : (
                  <Icon
                    name="add"
                    size={IconSize.lg}
                    color={theme.primary}
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
                  style={[s.inputField, composerExpanded && s.inputFieldExpanded]}
                  testID="chat-composer-field"
                  onPress={() => {
                    if (!math.mathBarOpen || showMathPreview) return;
                    math.closeMathBar();
                    requestAnimationFrame(() => inputRef.current?.focus());
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
                      composerExpanded ? s.inputExpanded : { height: inputHeight },
                      parkInput ? s.inputParked : null,
                    ]}
                    placeholder={showMathPreview ? "" : t("chat.placeholder")}
                    placeholderTextColor={theme.textDisabled}
                    value={input}
                    // Keep native input traits stable for the whole session:
                    // toggling correction midword races controlled math edits.
                    autoCorrect={false}
                    spellCheck={false}
                    autoCapitalize="none"
                    onChangeText={math.onChangeText}
                    onContentSizeChange={(event) => {
                      const measured = Math.ceil(event.nativeEvent.contentSize.height);
                      const next = Math.min(
                        COMPOSER_INPUT_MAX_HEIGHT,
                        Math.max(COMPOSER_INPUT_MIN_HEIGHT, measured),
                      );
                      setInputAtLimit(measured >= COMPOSER_INPUT_MAX_HEIGHT);
                      if (!composerExpanded) {
                        setInputHeight((current) => (current === next ? current : next));
                      }
                    }}
                    onSelectionChange={math.onSelectionChange}
                    selection={
                      showMathPreview
                        ? (math.forcedSelection ?? math.selection)
                        : undefined
                    }
                    caretHidden={showMathPreview || math.mathBarOpen}
                    pointerEvents={parkInput || math.mathBarOpen ? "none" : "auto"}
                    showSoftInputOnFocus={!math.mathBarOpen}
                    onFocus={() => {
                      onCloseAttachSheet();
                      liveTalkChrome?.onYield();
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
                    <Icon name="stop" size={14} color={theme.onPrimary} />
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
                            size={18}
                            color={isOffline ? theme.textTertiary : theme.onPrimary}
                          />
                        )}
                      </Pressable>
                    ) : null}
                  </>
                )}
              </View>
            </View>
            {showTokenHint ? (
              <Text
                style={s.tokenHint}
                testID="composer-token-hint"
                accessibilityRole="text"
              >
                {t("chat.draft_tokens", { count: draftTokens })}
              </Text>
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
              onNextSlot={math.nextSlot}
              onPrevSlot={math.prevSlot}
              onStepCaret={math.stepCaret}
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
      backgroundColor: theme.composerBg,
      paddingHorizontal: Space.sm,
      paddingTop: 2,
    },
    composerDocked: {
      overflow: "visible",
      backgroundColor: theme.composerBg,
      paddingHorizontal: Space.sm,
      paddingTop: 2,
    },
    composerBlockExpanded: {
      zIndex: 200,
      backgroundColor: theme.bg,
    },
    expandedFill: { flex: 1, minHeight: 0 },
    composerAnchor: { position: "relative", overflow: "visible" },
    composer: { paddingVertical: 6, overflow: "visible" },
    inputStack: { position: "relative", overflow: "visible" },
    liveTalkRow: {
      flexDirection: "row",
      alignItems: "flex-end",
      gap: Space.xs,
    },
    inputWrap: {
      backgroundColor: theme.inputBg,
      borderRadius: Radius.composer,
      paddingHorizontal: Space.sm,
      paddingTop: Space.xs,
      paddingBottom: Space.xs,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.composerBorder,
    },
    inputWrapFlex: { flex: 1, minWidth: 0 },
    inputWrapExpanded: { flex: 1, minHeight: 0 },
    tokenHint: {
      marginTop: Space.xxs,
      marginLeft: 40,
      ...Type.meta,
      color: theme.textTertiary,
    },
    sendStatus: {
      marginTop: Space.xxs,
      marginLeft: 40,
      ...Type.meta,
      color: theme.textSecondary,
    },
    inputRowMain: { flexDirection: "row", alignItems: "flex-end", gap: Space.xs },
    inputRowMainExpanded: { flex: 1, minHeight: 0 },
    inputField: { flex: 1, justifyContent: "center", minHeight: 22, position: "relative" },
    inputFieldExpanded: { justifyContent: "flex-start", minHeight: 0 },
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
      width: Space.minTouch,
      height: Space.minTouch,
      borderRadius: Space.minTouch / 2,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      backgroundColor: theme.surface,
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
      fontSize: Type.body.fontSize,
      color: theme.text,
      // Let the native line box scale with Dynamic Type. The bounds only
      // control when the multiline input starts scrolling.
      maxHeight: COMPOSER_INPUT_MAX_HEIGHT,
      paddingVertical: 0,
      minHeight: COMPOSER_INPUT_MIN_HEIGHT,
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
      width: Space.minTouch,
      height: Space.minTouch,
      borderRadius: Radius.full,
      backgroundColor: theme.primary,
      alignItems: "center",
      justifyContent: "center",
    },
    sendBtnSlot: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "flex-end",
      gap: 6,
      minHeight: Space.minTouch,
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
    scanHintText: { flex: 1, fontSize: 13, color: theme.text },
    scanHintCta: { fontSize: 13, fontWeight: "700", color: theme.primary },
  });
}
