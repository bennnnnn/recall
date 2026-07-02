import { useMemo } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { AttachmentSourceSheet, type AttachmentSource } from "@/components/AttachmentSourceSheet";
import { ComposerAttachmentPreview } from "@/components/ComposerAttachmentPreview";
import { SuggestedRemindersNudge } from "@/components/SuggestedRemindersNudge";
import type { PendingAttachment } from "@/lib/attachments";
import { Theme, useTheme } from "@/lib/theme";

export const COMPOSER_HEIGHT = 100;
export const COMPOSER_IMAGE_PREVIEW_EXTRA = 84;
export const COMPOSER_FILE_PREVIEW_EXTRA = 44;

export function composerAttachmentExtra(attachment: PendingAttachment | null): number {
  if (!attachment) return 0;
  return attachment.kind === "image" ? COMPOSER_IMAGE_PREVIEW_EXTRA : COMPOSER_FILE_PREVIEW_EXTRA;
}

type ModelOption = { id: string; label: string };

type Props = {
  visible: boolean;
  bottom: number;
  paddingBottom: number;
  token: string | null;
  input: string;
  onChangeInput: (text: string) => void;
  streaming: boolean;
  attachBusy: boolean;
  pendingAttachment: PendingAttachment | null;
  onRemoveAttachment: () => void;
  editingMessageId: string | null;
  onCancelEdit: () => void;
  showModelPicker: boolean;
  attachSheetOpen: boolean;
  modelOptions: ModelOption[];
  selectedModel: string;
  selectedModelLabel: string;
  onToggleModelPicker: () => void;
  onSelectModel: (id: string) => void;
  onClosePickers: () => void;
  onPickAttachment: () => void;
  onAttachmentSource: (source: AttachmentSource) => void;
  onSend: () => void;
  onStop: () => void;
  isOffline: boolean;
};

export function ChatComposer({
  visible,
  bottom,
  paddingBottom,
  token,
  input,
  onChangeInput,
  streaming,
  attachBusy,
  pendingAttachment,
  onRemoveAttachment,
  editingMessageId,
  onCancelEdit,
  showModelPicker,
  attachSheetOpen,
  modelOptions,
  selectedModel,
  selectedModelLabel,
  onToggleModelPicker,
  onSelectModel,
  onClosePickers,
  onPickAttachment,
  onAttachmentSource,
  onSend,
  onStop,
  isOffline,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  if (!visible) return null;

  return (
    <View style={[s.composerBlock, { bottom, paddingBottom }]}>
      {showModelPicker ? (
        <View style={s.picker}>
          {modelOptions.map((opt) => {
            const active = opt.id === selectedModel;
            return (
              <Pressable
                key={opt.id}
                style={[s.pickerItem, active && s.pickerItemActive]}
                onPress={() => onSelectModel(opt.id)}
              >
                <Text
                  style={[s.pickerLabel, active && s.pickerLabelActive, { flex: 1 }]}
                  numberOfLines={1}
                >
                  {opt.label}
                </Text>
                {active ? <Text style={s.pickerCheck}>✓</Text> : null}
              </Pressable>
            );
          })}
        </View>
      ) : null}

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
        {attachSheetOpen ? (
          <View style={s.attachMenuFloat} pointerEvents="box-none">
            <AttachmentSourceSheet onSelect={onAttachmentSource} />
          </View>
        ) : null}
        <View style={s.composer}>
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
                disabled={attachBusy || streaming}
                hitSlop={6}
                accessibilityLabel={t("chat.attach_a11y")}
              >
                <Ionicons name="attach-outline" size={22} color={theme.primary} />
              </Pressable>
              <TextInput
                style={s.input}
                placeholder={t("chat.placeholder")}
                placeholderTextColor={theme.textTertiary}
                value={input}
                onChangeText={onChangeInput}
                onFocus={onClosePickers}
                multiline
                returnKeyType="default"
              />
              <View style={s.sendBtnSlot}>
                {streaming ? (
                  <Pressable style={s.sendBtn} onPress={onStop}>
                    <Text style={s.sendIcon}>■</Text>
                  </Pressable>
                ) : input.trim() || pendingAttachment ? (
                  <Pressable
                    style={[s.sendBtn, isOffline && s.sendBtnDisabled]}
                    onPress={onSend}
                    accessibilityLabel={isOffline ? t("chat.offline_title") : undefined}
                    accessibilityHint={isOffline ? t("chat.offline_body") : undefined}
                  >
                    <Text style={[s.sendIcon, isOffline && s.sendIconDisabled]}>↑</Text>
                  </Pressable>
                ) : null}
              </View>
            </View>
            {modelOptions.length > 1 ? (
            <View style={s.composerMetaRow}>
                <Pressable
                  style={[s.modelPill, { maxWidth: 160 }]}
                  onPress={onToggleModelPicker}
                  hitSlop={6}
                >
                  <Text style={s.modelPillText} numberOfLines={1}>
                    {selectedModelLabel}
                  </Text>
                  <Ionicons
                    name={showModelPicker ? "chevron-up" : "chevron-down"}
                    size={12}
                    color={theme.textTertiary}
                  />
                </Pressable>
            </View>
            ) : null}
          </View>
        </View>
      </View>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    composerBlock: {
      position: "absolute",
      left: 0,
      right: 0,
      zIndex: 110,
      backgroundColor: theme.bg,
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
      borderRadius: 12,
      backgroundColor: theme.primaryLight,
    },
    editBannerText: { fontSize: 13, fontWeight: "600", color: theme.primary },
    editBannerCancel: { fontSize: 13, fontWeight: "600", color: theme.textSecondary },
    attachMenuFloat: {
      position: "absolute",
      left: 0,
      right: 14,
      bottom: "100%",
      marginBottom: 6,
      zIndex: 2,
    },
    composer: { paddingVertical: 6 },
    inputWrap: {
      backgroundColor: theme.surface,
      borderRadius: 20,
      paddingHorizontal: 12,
      paddingTop: 8,
      paddingBottom: 6,
    },
    inputRowMain: { flexDirection: "row", alignItems: "flex-end", gap: 8 },
    attachBtn: {
      width: 32,
      height: 32,
      alignItems: "center",
      justifyContent: "center",
      marginBottom: 1,
    },
    input: {
      flex: 1,
      fontSize: 16,
      color: theme.text,
      maxHeight: 100,
      paddingVertical: 0,
      minHeight: 22,
    },
    composerMetaRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "flex-start",
      marginTop: 6,
      gap: 8,
    },
    modelPill: {
      flexDirection: "row",
      alignItems: "center",
      gap: 4,
      paddingVertical: 2,
      paddingRight: 2,
    },
    modelPillText: { fontSize: 12, fontWeight: "600", color: theme.textSecondary },
    sendBtn: {
      width: 34,
      height: 34,
      borderRadius: 17,
      backgroundColor: theme.primary,
      alignItems: "center",
      justifyContent: "center",
    },
    sendBtnSlot: {
      width: 34,
      height: 35,
      alignItems: "center",
      justifyContent: "flex-end",
    },
    sendIcon: { color: theme.onPrimary, fontSize: 18, fontWeight: "700" },
    sendBtnDisabled: { backgroundColor: theme.border },
    sendIconDisabled: { color: theme.textTertiary },
    picker: {
      marginBottom: 8,
      backgroundColor: theme.bg,
      borderRadius: 16,
      borderWidth: 1,
      borderColor: theme.border,
      boxShadow: "0 -4 12 0 rgba(0, 0, 0, 0.12)",
      elevation: 8,
      overflow: "hidden",
    },
    pickerItem: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      paddingHorizontal: 16,
      paddingVertical: 12,
    },
    pickerItemActive: { backgroundColor: theme.primaryLight },
    pickerLabel: { fontSize: 15, fontWeight: "600", color: theme.text },
    pickerLabelActive: { color: theme.primary },
    pickerCheck: { color: theme.primary, fontWeight: "700", fontSize: 15 },
  });
}
