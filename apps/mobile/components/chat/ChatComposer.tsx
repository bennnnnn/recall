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
import { Icon } from "@/components/Icon";
import { useTranslation } from "react-i18next";

import { LiveTalkButton } from "@/components/chat/LiveTalkButton";
import { VoiceComposerWaveform } from "@/components/chat/VoiceComposerWaveform";
import { VoiceMicButton } from "@/components/chat/VoiceMicButton";
import {
  MathDraftPreview,
  MATH_DRAFT_PREVIEW_HEIGHT,
  draftShowsMathPreview,
} from "@/components/chat/MathDraftPreview";
import { MathComposerCaret } from "@/components/chat/MathComposerCaret";
import { MathKeyboardBar } from "@/components/chat/MathKeyboardBar";
import { ComposerAttachmentPreview } from "@/components/ComposerAttachmentPreview";
import { SuggestedRemindersNudge } from "@/components/SuggestedRemindersNudge";
import {
  useComposerDraftApiOptional,
  useComposerDraftValueOptional,
} from "@/contexts/ComposerDraftContext";
import { useMathKeyboardInsert } from "@/hooks/useMathKeyboardInsert";
import type { PendingAttachment } from "@/lib/attachments";
import { composerShowsMic, composerShowsSend } from "@/lib/chatComposerLogic";
import { estimateTokens, shouldShowDraftTokenHint } from "@/lib/estimateTokens";
import { textLooksLikeMath } from "@/lib/math/mathComposerIntent";
import { caretAfterExpression, caretBeforeExpression } from "@/lib/mathDraftSlots";
import { Radius } from "@/lib/radius";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

function noopComposerInput(_text: string) {}

export const COMPOSER_HEIGHT = 88;
export const COMPOSER_IMAGE_PREVIEW_EXTRA = 84;
export const COMPOSER_FILE_PREVIEW_EXTRA = 44;
const MATH_KEYBOARD_CHIP_HEIGHT = 44;
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
  token: string | null;
  /** Tests pass these; production reads ComposerDraftContext. */
  input?: string;
  onChangeInput?: (text: string) => void;
  streaming: boolean;
  attachBusy: boolean;
  attachPicking?: boolean;
  sendBusy?: boolean;
  pendingAttachment: PendingAttachment | null;
  onRemoveAttachment: () => void;
  editingMessageId: string | null;
  onCancelEdit: () => void;
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
  /** When true, parent owns absolute bottom positioning (e.g. quiz dock). */
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
  token,
  input: inputProp,
  onChangeInput: onChangeInputProp,
  streaming,
  attachBusy,
  attachPicking = false,
  sendBusy = false,
  pendingAttachment,
  onRemoveAttachment,
  editingMessageId,
  onCancelEdit,
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
  docked = false,
  onOpenMathScanner,
  onMathChromeHeightChange,
  mathContext = false,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const draft = useComposerDraftValueOptional();
  const draftApi = useComposerDraftApiOptional();
  const input = inputProp ?? draft?.input ?? "";
  const onChangeInput =
    onChangeInputProp ??
    (draftApi ? (text: string) => draftApi.setInput(text) : noopComposerInput);
  const [scanHint, setScanHint] = useState(false);
  const inputRef = useRef<TextInput>(null);
  const math = useMathKeyboardInsert({
    input,
    setInput: onChangeInput,
    onImageOnlyPaste: onOpenMathScanner ? () => setScanHint(true) : undefined,
  });
  const showMathPreview = draftShowsMathPreview(input);
  const showMathChip =
    !math.mathBarOpen && (mathContext || textLooksLikeMath(input));
  const draftTokens = estimateTokens(input);
  const showTokenHint = shouldShowDraftTokenHint(draftTokens);
  const mathChromeHeight =
    (math.mathBarOpen ? math.padHeight : showMathChip ? MATH_KEYBOARD_CHIP_HEIGHT : 0) +
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

  const onToggleMathBar = useCallback(() => {
    const wasOpen = math.mathBarOpen;
    math.toggleMathBar();
    if (wasOpen) {
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [math.mathBarOpen, math.toggleMathBar]);

  if (!visible) return null;

  const hasSendableContent = Boolean(input.trim() || pendingAttachment);
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

  const blockStyle = docked ? s.composerDocked : s.composerBlock;
  const containerStyle = animatedContainerStyle
    ? [blockStyle, animatedContainerStyle]
    : [blockStyle, { bottom, paddingBottom }];

  return (
    <Animated.View style={containerStyle}>
      <View style={s.composerAnchor}>
        <SuggestedRemindersNudge token={token} />
        {editingMessageId ? (
          <View style={s.editBanner}>
            <Text style={s.editBannerText}>{t("chat.editing_message")}</Text>
            <Pressable onPress={onCancelEdit}>
              <Text style={s.editBannerCancel}>{t("common.cancel")}</Text>
            </Pressable>
          </View>
        ) : null}
        <View style={s.composer}>
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
                <Text style={s.scanHintDismiss}>×</Text>
              </Pressable>
            </View>
          ) : null}
          {showMathChip ? (
            <View style={s.chipRow}>
              <Pressable
                onPress={onToggleMathBar}
                style={({ pressed }) => [s.chip, pressed && s.chipPressed]}
                accessibilityRole="button"
                accessibilityLabel={t("chat.math_keyboard_show")}
                testID="math-keyboard-toggle"
              >
                <Icon name="keypad-outline" size={18} color={theme.primary} />
              </Pressable>
            </View>
          ) : null}
          <View style={s.inputWrap}>
            {pendingAttachment ? (
              <ComposerAttachmentPreview
                attachment={pendingAttachment}
                uploading={attachBusy}
                onRemove={onRemoveAttachment}
              />
            ) : null}
            <View style={s.inputRowMain}>
              <Pressable
                style={s.attachBtn}
                onPress={onPickAttachment}
                disabled={attachBusy || attachPicking || sendBusy || streaming}
                hitSlop={{ top: 14, bottom: 14, left: 14, right: 14 }}
                accessibilityRole="button"
                accessibilityLabel={t("chat.attach_a11y")}
                accessibilityState={{
                  disabled: attachBusy || attachPicking || sendBusy || streaming,
                  busy: attachPicking,
                }}
              >
                {attachPicking ? (
                  <ActivityIndicator size="small" color={theme.primary} />
                ) : (
                  <Icon name="attach-outline" size={22} color={theme.primary} />
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
                  style={s.inputField}
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
                    style={[s.input, parkInput ? s.inputParked : null]}
                    placeholder={showMathPreview ? "" : t("chat.placeholder")}
                    placeholderTextColor={theme.textDisabled}
                    value={input}
                    onChangeText={math.onChangeText}
                    onSelectionChange={math.onSelectionChange}
                    selection={
                      showMathPreview
                        ? (math.forcedSelection ?? math.selection)
                        : undefined
                    }
                    caretHidden={showMathPreview || math.mathBarOpen}
                    pointerEvents={parkInput || math.mathBarOpen ? "none" : "auto"}
                    showSoftInputOnFocus={!math.mathBarOpen}
                    onFocus={onCloseAttachSheet}
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
                    <Text style={s.sendIcon}>■</Text>
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
                          <Text style={[s.sendIcon, isOffline && s.sendIconDisabled]}>
                            ↑
                          </Text>
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
      backgroundColor: theme.composerBg,
      paddingHorizontal: 12,
      paddingTop: 2,
    },
    composerDocked: {
      backgroundColor: theme.composerBg,
      paddingHorizontal: 12,
      paddingTop: 2,
    },
    composerAnchor: { position: "relative" },
    editBanner: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      marginHorizontal: 4,
      marginBottom: 6,
      paddingHorizontal: 12,
      paddingVertical: 8,
      borderRadius: Radius.md,
      backgroundColor: theme.primaryLight,
    },
    editBannerText: { fontSize: 13, fontWeight: "600", color: theme.primary },
    editBannerCancel: { fontSize: 13, fontWeight: "600", color: theme.textSecondary },
    composer: { paddingVertical: 6 },
    inputWrap: {
      backgroundColor: theme.inputBg,
      borderRadius: Radius.lg,
      paddingHorizontal: 12,
      paddingTop: 8,
      paddingBottom: 8,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.composerBorder,
    },
    tokenHint: {
      marginTop: 4,
      marginLeft: 40,
      ...Type.meta,
      color: theme.textTertiary,
    },
    inputRowMain: { flexDirection: "row", alignItems: "flex-end", gap: 8 },
    inputField: { flex: 1, justifyContent: "center", minHeight: 22, position: "relative" },
    emptyCaret: {
      position: "absolute",
      left: 0,
      top: 2,
      bottom: 2,
      justifyContent: "center",
      zIndex: 2,
    },
    attachBtn: {
      width: 44,
      height: 44,
      alignItems: "center",
      justifyContent: "center",
      marginBottom: 0,
    },
    chipRow: {
      height: MATH_KEYBOARD_CHIP_HEIGHT,
      marginBottom: 4,
      flexDirection: "row",
      alignItems: "center",
    },
    chip: {
      minWidth: 44,
      minHeight: 44,
      height: 44,
      paddingHorizontal: 10,
      borderRadius: 16,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: theme.surfaceAlt,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    chipPressed: { opacity: 0.55 },
    input: {
      flex: 1,
      fontSize: Type.body.fontSize,
      lineHeight: Type.body.lineHeight,
      color: theme.text,
      maxHeight: Type.body.lineHeight * 6,
      paddingVertical: 0,
      minHeight: Type.body.lineHeight,
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
      width: 44,
      height: 44,
      borderRadius: 22,
      backgroundColor: theme.primary,
      alignItems: "center",
      justifyContent: "center",
    },
    sendBtnSlot: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "flex-end",
      gap: 6,
      minHeight: 44,
    },
    sendIcon: { color: theme.onPrimary, fontSize: 18, fontWeight: "700" },
    sendBtnDisabled: { backgroundColor: theme.border },
    sendIconDisabled: { color: theme.textTertiary },
    scanHint: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      marginBottom: 6,
      paddingHorizontal: 10,
      paddingVertical: 8,
      borderRadius: 10,
      backgroundColor: theme.primaryLight,
    },
    scanHintText: { flex: 1, fontSize: 13, color: theme.text },
    scanHintCta: { fontSize: 13, fontWeight: "700", color: theme.primary },
    scanHintDismiss: { fontSize: 18, color: theme.textSecondary, paddingHorizontal: 4 },
  });
}
