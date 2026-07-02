import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/contexts/AuthContext";
import { api, type Template } from "@/lib/api";

export function useTemplates(enabled: boolean) {
  const { token } = useAuth();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const refresh = useCallback(async () => {
    if (!token || !enabled) return;
    setLoading(true);
    setError(false);
    try {
      const items = await api.listTemplates(token);
      setTemplates(items);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [token, enabled]);

  useEffect(() => {
    if (!enabled) return;
    void refresh();
  }, [enabled, refresh]);

  return { templates, loading, error, refresh };
}
