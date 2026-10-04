import { useMemo, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import type { JobSearchDashboard } from "@/lib/api";
import { Button } from "@/ui/controls/Button";
import { StatusPill } from "@/ui/feedback/StatusPill";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";
import { useTheme } from "@/lib/theme";

export function SearchStatusHeader({ dashboard, paid, onAsk }: {
  dashboard: JobSearchDashboard; paid: boolean;
  onAsk: () => void;
}) {
  const { t } = useTranslation();
  const [now, setNow] = useState<number>(() => Date.now());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(timer); }, []);
  const C = useTheme();
  const profile = dashboard.profile;
  const s = useMemo(() => StyleSheet.create({
    wrap: { gap: Space.sm }, line: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: Space.xs },
    scope: { ...Type.secondary, color: C.text }, meta: { ...Type.compact, color: C.textSecondary },
    notice: { ...Type.secondary, color: C.warning }, actions: { flexDirection: "row", flexWrap: "wrap", gap: Space.xs },
  }), [C]);
  if (!profile) return null;
  const run = dashboard.latest_run;
  const running = run?.state === "queued" || run?.state === "running";
  const state = !paid ? "expired_pro" : running ? "running" : profile.status;
  const scope = profile.included_locations?.length
    ? profile.included_locations.map(place => [place.city, place.region, place.country].filter(Boolean).join(", ")).join(" · ")
    : profile.location || t("my_job.worldwide");
  const blocked = Boolean(dashboard.cooldown_until && Date.parse(dashboard.cooldown_until) > now);
  const date = (value: string) => new Date(value).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  return <View style={s.wrap}>
    <View style={s.line}>
      {state !== "active" ? <StatusPill label={t(`my_job.run_${state}`)} tone={running ? "accent" : profile.status === "paused" ? "neutral" : "success"} /> : null}
      <Text style={s.scope}>{scope}</Text>
    </View>
    <Text style={s.meta}>{t("my_job.last_checked", { date: profile.last_run_at ? date(profile.last_run_at) : t("my_job.not_checked") })}</Text>
    {paid && profile.status === "active" ? <Text style={s.meta}>{t("my_job.next_delivery", { date: date(profile.next_run_at) })}</Text> : null}
    <View style={s.actions}>
      <Button title={t("my_job.ask_recall")} icon="sparkles" variant="secondary" style={{ paddingHorizontal: Space.sm }} onPress={onAsk} />
    </View>
    {dashboard.premium_enabled === false ? <Text style={s.meta}>{t("my_job.rollout_pending")}</Text> : null}
    {!paid ? <Text style={s.notice}>{t("my_job.expired_pro_body")}</Text> : null}
    {paid && dashboard.manual_remaining === 0 ? <Text style={s.notice}>{t("my_job.manual_quota")}</Text> : blocked ? <Text style={s.meta}>{t("my_job.cooldown")}</Text> : null}
    {run?.partial ? <Text style={s.notice}>{t("my_job.partial_results")}</Text> : null}
    {run && ["failed", "limited", "cancelled"].includes(run.state) ? <Text accessibilityRole="alert" style={s.notice}>{run.failure_reason || t("my_job.run_failed_body")}</Text> : null}
    {profile.needs_review ? <Text style={s.notice}>{t("my_job.preferences_review")}</Text> : null}
  </View>;
}
