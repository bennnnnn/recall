import { useCallback } from "react";
import { useTranslation } from "react-i18next";

import type { ClientGeo } from "@/lib/clientGeo";
import type { Message, User } from "@/lib/api";
import { resolveClientGeoForQuery } from "@/lib/resolveClientGeoForQuery";

type Params = {
  token: string | null;
  messages: Message[];
  user: User | null;
  updateUser: (patch: Partial<User>) => Promise<void>;
  regenerateResponse: (model?: string | null, clientGeo?: ClientGeo | null) => Promise<void>;
};

export function useChatRegenerate({
  token,
  messages,
  user,
  updateUser,
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
        updateUser,
        user?.location_enabled ?? false,
      );
      if (!result.ok) return;
      await regenerateResponse(model, result.clientGeo);
    },
    [token, messages, regenerateResponse, t, updateUser, user?.location_enabled],
  );
}
