import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { useCalendarProposal } from "@/hooks/useCalendarProposal";
import {
  type CalendarProposal,
  formatProposalWhen,
} from "@/lib/calendarProposal";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  proposal: CalendarProposal;
  disabled?: boolean;
};

export function CalendarProposalCard({ proposal, disabled }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = makeStyles(theme);
  const { busy, done, confirm } = useCalendarProposal(proposal);
  const [error, setError] = useState<string | null>(null);

  const onConfirm = async () => {
    if (busy || done || disabled) return;
    setError(null);
    if (!(await confirm())) {
      setError(t("calendar.proposal_failed"));
    }
  };

  return (
    <View style={s.card}>
      <View style={s.header}>
        <Icon name="calendar-outline" size={20} color={theme.primary} />
        <Text style={s.title} numberOfLines={2}>
          {proposal.title}
        </Text>
      </View>
      <Text style={s.when}>{formatProposalWhen(proposal.start_at, proposal.end_at)}</Text>
      {proposal.location ? (
        <Text style={s.meta} numberOfLines={2}>
          {proposal.location}
        </Text>
      ) : null}
      {error ? <Text style={s.error}>{error}</Text> : null}
      {done ? (
        <View style={s.doneRow}>
          <Icon name="checkmark-circle" size={18} color={theme.primary} />
          <Text style={s.doneText}>{t("calendar.proposal_added")}</Text>
        </View>
      ) : (
        <Button
          title={t("calendar.proposal_confirm")}
          onPress={() => void onConfirm()}
          loading={busy}
          disabled={disabled}
          style={s.btn}
        />
      )}
    </View>
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    card: {
      marginTop: 10,
      padding: 14,
      borderRadius: 14,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      backgroundColor: theme.surface,
      gap: 8,
    },
    header: { flexDirection: "row", alignItems: "center", gap: 10 },
    title: { flex: 1, fontSize: 16, fontWeight: "700", color: theme.text },
    when: { fontSize: 14, fontWeight: "600", color: theme.textSecondary },
    meta: { fontSize: 13, color: theme.textTertiary },
    error: { fontSize: 13, color: theme.danger },
    btn: {
      marginTop: 4,
    },
    doneRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 4 },
    doneText: { fontSize: 14, fontWeight: "600", color: theme.primary },
  });
