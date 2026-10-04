import { useEffect, useMemo, useState } from "react";
import { View } from "react-native";
import { useRouter } from "expo-router";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/contexts/AuthContext";
import { api, type JobMatch } from "@/lib/api";
import { JobMatchCard } from "./JobMatchCard";
import { StateView } from "@/ui/feedback/StateView";
import { Space } from "@/lib/space";

/** Hydrate persisted IDs: a model-written fence cannot invent jobs or ownership. */
export function JobResultsBlock({ content }: { content: string }) {
  const { token, user } = useAuth();
  const router = useRouter();
  const { t } = useTranslation();
  const [matches, setMatches] = useState<JobMatch[]>([]);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const ids = useMemo(() => {
    try {
      const data: unknown = JSON.parse(content);
      if (!data || typeof data !== "object" || !("matches" in data) || !Array.isArray(data.matches)) return [];
      return data.matches.flatMap((item: unknown) => item && typeof item === "object" && "id" in item &&
        typeof item.id === "string" && /^[0-9a-f-]{36}$/i.test(item.id) ? [item.id] : []).slice(0, 15);
    } catch { return []; }
  }, [content]);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setMatches([]);
    setError(false);
    if (!token || !ids.length) { setLoading(false); return () => { alive = false; }; }
    void Promise.allSettled(ids.map(id => api.getJobMatch(token, id))).then(results => {
      if (!alive) return;
      setMatches(results.flatMap(result => result.status === "fulfilled" ? [result.value] : []));
      setError(results.some(result => result.status === "rejected"));
      setLoading(false);
    });
    return () => { alive = false; };
  }, [token, user?.id, ids]);
  return <View style={{ gap: Space.sm }}>
    {loading ? <StateView variant="loading" compact title={t("my_job.run_running")} /> : null}
    {error || (!loading && !matches.length) ? <StateView variant="error" compact title={t("my_job.refresh_error")} /> : null}
    {matches.map(match => <JobMatchCard key={match.id} match={match} readOnly
      onStatus={() => undefined} onSavedChange={() => undefined} onPress={() => router.push(`/my-job/match/${match.id}`)} />)}
  </View>;
}
