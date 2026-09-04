import { useEffect, useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";

import { CopyButton } from "@/components/CopyButton";
import { Icon } from "@/components/Icon";
import { NewChatIcon } from "@/components/NewChatIcon";
import { CardShell } from "@/components/rich/CardShell";
import { GmailMark } from "@/components/rich/chatgptDraftIcons";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useEmailCardPersist } from "@/hooks/useEmailCardPersist";
import { fullEmailText } from "@/lib/emailCompose";
import { openGmailCompose } from "@/lib/openGmailCompose";
import { notifySuccess, tap } from "@/lib/haptics";
import { inkIconColor } from "@/lib/icons";
import { EmailDraft } from "@/lib/richBlocks";
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
  const feedback = useActionFeedbackOptional();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [gmailOpening, setGmailOpening] = useState(false);
  const [editing, setEditing] = useState(false);
  const [fields, setFields] = useState(() => draftFields(draft));
  const fieldsRef = useRef(fields);
  fieldsRef.current = fields;

  const draftTo = draft.to;
  const draftSubject = draft.subject;
  const draftBody = draft.body;

  useEffect(() => {
    if (editing) return;
    setFields(draftFields({ to: draftTo, subject: draftSubject, body: draftBody }));
  }, [draftTo, draftSubject, draftBody, editing]);

  const currentDraft = useMemo(() => toDraft(fields), [fields]);
  const persistNow = useEmailCardPersist(currentDraft, editing);
  const copyPayload = fullEmailText(currentDraft);

  const onGmail = async () => {
    if (gmailOpening) return;
    tap();
    setGmailOpening(true);
    try {
      const result = await openGmailCompose(currentDraft);
      if (result === "copied_only") {
        if (feedback) feedback.success(t("chat.email_card_gmail_copied"));
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
      const prev = fieldsRef.current;
      const next = {
        to: prev.to.trim(),
        subject: prev.subject.trim(),
        body: prev.body.trimEnd(),
      };
      fieldsRef.current = next;
      setFields(next);
      setEditing(false);
      void persistNow(toDraft(next));
      return;
    }
    setEditing(true);
  };

  return (
    <CardShell
      label={t("chat.email_card_title")}
      icon="mail-outline"
      accent={false}
      headerActions={
        <>
          <Pressable
            style={[s.iconBtn, editing && s.iconBtnActive]}
            onPress={toggleEditing}
            hitSlop={6}
            accessibilityRole="button"
            accessibilityLabel={
              editing ? t("chat.email_card_done") : t("chat.email_card_edit")
            }
          >
            {editing ? (
              <Icon name="checkmark-outline" size={20} />
            ) : (
              <NewChatIcon size={20} color={inkIconColor(theme)} />
            )}
          </Pressable>
          <CopyButton
            text={copyPayload}
            accessibilityLabel={t("chat.email_card_copy")}
          />
          <Pressable
            style={[s.iconBtn, gmailOpening && s.gmailBtnBusy]}
            onPress={() => void onGmail()}
            hitSlop={6}
            accessibilityRole="button"
            accessibilityLabel={t("chat.email_card_gmail")}
            disabled={gmailOpening || editing}
          >
            <GmailMark size={18} />
          </Pressable>
        </>
      }
    >
      <View style={s.body}>
        {editing ? (
          <>
            <Text style={s.fieldLabel}>{t("chat.email_card_to")}</Text>
            <TextInput
              style={s.input}
              value={fields.to}
              onChangeText={(to) => {
                setFields((prev) => {
                  const next = { ...prev, to };
                  fieldsRef.current = next;
                  return next;
                });
              }}
              placeholder={t("chat.email_card_to_placeholder")}
              placeholderTextColor={theme.textDisabled}
              autoCapitalize="none"
              keyboardType="email-address"
              autoCorrect={false}
            />
            <Text style={s.fieldLabel}>{t("chat.email_card_subject")}</Text>
            <TextInput
              style={s.input}
              value={fields.subject}
              onChangeText={(subject) => {
                setFields((prev) => {
                  const next = { ...prev, subject };
                  fieldsRef.current = next;
                  return next;
                });
              }}
              placeholder={t("chat.email_card_subject_placeholder")}
              placeholderTextColor={theme.textDisabled}
            />
            <TextInput
              style={[s.input, s.bodyInput]}
              value={fields.body}
              onChangeText={(body) => {
                setFields((prev) => {
                  const next = { ...prev, body };
                  fieldsRef.current = next;
                  return next;
                });
              }}
              multiline
              textAlignVertical="top"
              placeholder={t("chat.email_card_body_placeholder")}
              placeholderTextColor={theme.textDisabled}
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
    </CardShell>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    iconBtn: {
      width: 32,
      height: 32,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: 8,
    },
    iconBtnActive: { backgroundColor: t.primaryLight },
    gmailBtnBusy: { opacity: 0.6 },
    body: { gap: 8 },
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
    subject: {
      fontSize: 16,
      fontWeight: "700",
      lineHeight: 22,
      color: t.text,
    },
    bodyText: {
      fontSize: 16,
      lineHeight: 24,
      color: t.text,
    },
  });
}
