import { useCallback } from "react";
import { useTranslation } from "react-i18next";

import type { ClientGeo } from "@/lib/clientGeo";
import type { Message } from "@/lib/api";
import { resolveClientGeoForQuery } from "@/lib/resolveClientGeoForQuery";

type Params = {
  token: string | null;
  messages: Message[];
  mergeUser: (patch: { location: string; location_enabled: boolean }) => void;
  regenerateResponse: (model?: string | null, clientGeo?: ClientGeo | null) => Promise<void>;
};

export function useChatRegenerate({
  token,
  messages,
  mergeUser,
  regenerateResponse,
}: Params) {
  const { t } = useTranslation();

  return useCallback(
    async (model: string) => {
      if (!token) return;
      const lastUser = [...messages].reverse().find((m) => m.role === "user");
      const result = await resolveClientGeoForQuery(
        token,
        lastUser?.content ?? "",
        t,
        mergeUser,
      );
      if (!result.ok) return;
      await regenerateResponse(model, result.clientGeo);
    },
    [token, messages, regenerateResponse, t, mergeUser],
  );
}
