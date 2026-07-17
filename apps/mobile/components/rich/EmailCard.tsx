import { useEffect, useMemo, useRef, useState } from "react";
import { Alert, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { fullEmailText } from "@/lib/emailCompose";
import { openGmailCompose } from "@/lib/openGmailCompose";
import { EmailDraft } from "@/lib/richBlocks";
import { notifySuccess, tap } from "@/lib/haptics";
import { Theme, useTheme } from "@/lib/theme";

type Props = { draft: EmailDraft };

function draftFields(draft: EmailDraft) {
  return {
    to: draft.to ?? "",
    subject: draft.subject ?? "",
    body: draft.body,
  };
}

function toDraft(fields: { to: string; subject: string; body: string }): EmailDraft {
  const to = fields.to.trim();
  const subject = fields.subject.trim();
  const body = fields.body.trim();
  return {
    ...(to ? { to } : {}),
    ...(subject ? { subject } : {}),
    body: body || fields.body,
  };
}

export function EmailCard({ draft }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [copied, setCopied] = useState(false);
  const [gmailOpening, setGmailOpening] = useState(false);
  const [editing, setEditing] = useState(false);
  const [fields, setFields] = useState(() => draftFields(draft));
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setFields(draftFields(draft));
    setEditing(false);
  }, [draft.to, draft.subject, draft.body]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const currentDraft = useMemo(() => toDraft(fields), [fields]);
  const copyPayload = fullEmailText(currentDraft);

  const onCopy = async () => {
    tap();
    await Clipboard.setStringAsync(copyPayload);
    setCopied(true);
    notifySuccess();
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setCopied(false), 1500);
  };

  const onGmail = async () => {
    if (gmailOpening) return;
    tap();
    setGmailOpening(true);
    try {
      const result = await openGmailCompose(currentDraft);
      if (result === "copied_only") {
        Alert.alert(t("chat.email_card_gmail"), t("chat.email_card_gmail_copied"));
      } else {
        notifySuccess();
      }
    } finally {
      setGmailOpening(false);
    }
  };

  const toggleEditing = () => {
    tap();
    if (editing) {
      setFields((prev) => ({
        to: prev.to.trim(),
        subject: prev.subject.trim(),
        body: prev.body.trimEnd(),
      }));
      setEditing(false);
      return;
    }
    setEditing(true);
  };

  return (
    <View style={s.wrap}>
      <View style={s.header}>
        <Text style={s.headerTitle}>{t("chat.email_card_title")}</Text>
        <View style={s.actions}>
          <Pressable
            style={[s.iconBtn, editing && s.iconBtnActive]}
            onPress={toggleEditing}
            hitSlop={6}
            accessibilityLabel={
              editing ? t("chat.email_card_done") : t("chat.email_card_edit")
            }
          >
            <Ionicons
              name={editing ? "checkmark-outline" : "create-outline"}
              size={20}
              color={editing ? theme.primary : theme.textSecondary}
            />
          </Pressable>
          <Pressable
            style={s.iconBtn}
            onPress={() => void onCopy()}
            hitSlop={6}
            accessibilityLabel={t("chat.email_card_copy")}
            disabled={editing}
          >
            <Ionicons
              name={copied ? "checkmark-outline" : "copy-outline"}
              size={20}
              color={copied ? theme.primary : theme.textSecondary}
            />
          </Pressable>
          <Pressable
            style={[s.gmailBtn, gmailOpening && s.gmailBtnBusy]}
            onPress={() => void onGmail()}
            hitSlop={6}
            accessibilityLabel={t("chat.email_card_gmail")}
            disabled={gmailOpening || editing}
          >
            <Ionicons name="mail-outline" size={16} color={theme.brand.gmail} />
            <Text style={s.gmailBtnText}>{t("rich.gmail")}</Text>
          </Pressable>
        </View>
      </View>
      <View style={s.body}>
        {editing ? (
          <>
            <Text style={s.fieldLabel}>{t("chat.email_card_to")}</Text>
            <TextInput
              style={s.input}
              value={fields.to}
              onChangeText={(to) => setFields((prev) => ({ ...prev, to }))}
              placeholder={t("chat.email_card_to_placeholder")}
              placeholderTextColor={theme.textTertiary}
              autoCapitalize="none"
              keyboardType="email-address"
              autoCorrect={false}
            />
            <Text style={s.fieldLabel}>{t("chat.email_card_subject")}</Text>
            <TextInput
              style={s.input}
              value={fields.subject}
              onChangeText={(subject) => setFields((prev) => ({ ...prev, subject }))}
              placeholder={t("chat.email_card_subject_placeholder")}
              placeholderTextColor={theme.textTertiary}
            />
            <TextInput
              style={[s.input, s.bodyInput]}
              value={fields.body}
              onChangeText={(body) => setFields((prev) => ({ ...prev, body }))}
              multiline
              textAlignVertical="top"
              placeholder={t("chat.email_card_body_placeholder")}
              placeholderTextColor={theme.textTertiary}
            />
          </>
        ) : (
          <>
            {currentDraft.to ? (
              <Text style={s.meta} selectable>
                <Text style={s.metaKey}>{t("chat.email_card_to")} </Text>
                {currentDraft.to}
              </Text>
            ) : null}
            {currentDraft.subject ? (
              <Text style={s.subject} selectable>
                {t("chat.email_card_subject")} {currentDraft.subject}
              </Text>
            ) : null}
            <Text style={s.bodyText} selectable>
              {currentDraft.body}
            </Text>
          </>
        )}
      </View>
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      alignSelf: "stretch",
      backgroundColor: t.surface,
      borderRadius: 16,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      marginVertical: 8,
      overflow: "hidden",
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: 14,
      paddingVertical: 12,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
    },
    headerTitle: { fontSize: 16, fontWeight: "700", color: t.text },
    actions: { flexDirection: "row", alignItems: "center", gap: 4 },
    iconBtn: {
      width: 36,
      height: 36,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: 8,
    },
    iconBtnActive: { backgroundColor: t.primaryLight },
    gmailBtn: {
      flexDirection: "row",
      alignItems: "center",
      gap: 4,
      paddingHorizontal: 10,
      paddingVertical: 6,
      borderRadius: 999,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      backgroundColor: t.bg,
    },
    gmailBtnBusy: { opacity: 0.6 },
    gmailBtnText: { fontSize: 13, fontWeight: "700", color: t.text },
    body: { paddingHorizontal: 14, paddingVertical: 14, gap: 8 },
    fieldLabel: {
      fontSize: 12,
      fontWeight: "700",
      color: t.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.4,
    },
    input: {
      backgroundColor: t.bg,
      borderRadius: 10,
      borderWidth: 1,
      borderColor: t.border,
      paddingHorizontal: 12,
      paddingVertical: 10,
      fontSize: 16,
      color: t.text,
    },
    bodyInput: { minHeight: 140, lineHeight: 24 },
    meta: { fontSize: 14, lineHeight: 20, color: t.textSecondary },
    metaKey: { fontWeight: "600", color: t.textTertiary },
    subject: { fontSize: 16, fontWeight: "700", lineHeight: 22, color: t.text },
    bodyText: { fontSize: 16, lineHeight: 24, color: t.text },
  });
}
