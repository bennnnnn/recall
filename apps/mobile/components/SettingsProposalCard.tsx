import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { useAppearance } from "@/contexts/AppearanceContext";
import { useAuth, useAuthToken } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { writeCachedUser } from "@/lib/cachedUser";
import type { AppearancePreference } from "@/lib/appearance";
import { normalizeAppearancePreference } from "@/lib/appearance";
import type { SettingsProposal } from "@/lib/settingsProposal";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  proposal: SettingsProposal;
  disabled?: boolean;
};

function isAppearance(value: string): value is AppearancePreference {
  return value === "light" || value === "dark" || value === "system";
}

export function SettingsProposalCard({ proposal, disabled }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = makeStyles(theme);
  const token = useAuthToken();
  const { mergeUser } = useAuth();
  const { setPreference } = useAppearance();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onConfirm = async () => {
    if (!token || busy || done || disabled) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.confirmSettingsProposal(token, proposal.proposal_id);
      mergeUser(result.user);
      void writeCachedUser(result.user);
      if (result.appearance && isAppearance(result.appearance)) {
        await setPreference(normalizeAppearancePreference(result.appearance));
      }
      setDone(true);
    } catch {
      setError(t("settings.proposal_failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={s.card}>
      <View style={s.header}>
        <Icon name="options-outline" size={20} color={theme.primary} />
        <Text style={s.title}>{t("settings.proposal_title")}</Text>
      </View>
      {proposal.changes.map((change) => (
        <Text key={`${change.field}:${change.value}`} style={s.change}>
          {t(`settings.field_${change.field}`, { defaultValue: change.field })} → {change.label}
        </Text>
      ))}
      {error ? <Text style={s.error}>{error}</Text> : null}
      {done ? (
        <View style={s.doneRow}>
          <Icon name="checkmark-circle" size={18} color={theme.primary} />
          <Text style={s.doneText}>{t("settings.proposal_applied")}</Text>
        </View>
      ) : (
        <Button
          title={t("settings.proposal_confirm")}
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
    change: { fontSize: 14, fontWeight: "600", color: theme.textSecondary },
    error: { fontSize: 13, color: theme.danger },
    btn: { marginTop: 4 },
    doneRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 4 },
    doneText: { fontSize: 14, fontWeight: "600", color: theme.primary },
  });
