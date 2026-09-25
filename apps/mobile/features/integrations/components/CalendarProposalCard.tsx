import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Icon } from "@/ui/icons/Icon";
import { useTranslation } from "react-i18next";

import { Button } from "@/ui/controls/Button";
import { useCalendarProposal } from "@/features/integrations/hooks/useCalendarProposal";
import {
  type CalendarProposal,
  formatProposalWhen,
} from "@/features/integrations/model/calendarProposal";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { IconSize } from "@/lib/icons";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";

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
        <Icon name="calendar-outline" size={IconSize.sm} color={theme.primary} />
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
      borderRadius: Radius.lg,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      backgroundColor: theme.surface,
      gap: Space.xs,
    },
    header: { flexDirection: "row", alignItems: "center", gap: 10 },
    title: { flex: 1, ...Type.body, ...Weight.bold, color: theme.text },
    when: { ...Type.label, color: theme.textSecondary },
    meta: { ...Type.compact, color: theme.textTertiary },
    error: { ...Type.compact, color: theme.danger },
    btn: {
      marginTop: Space.xxs,
    },
    doneRow: { flexDirection: "row", alignItems: "center", gap: Space.xs, marginTop: Space.xxs },
    doneText: { ...Type.label, color: theme.primary },
  });
