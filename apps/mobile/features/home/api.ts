import { request } from "@/lib/api/client";
import type { HomeScreen } from "@/lib/api/types";

export const homeApi = {
  getHomeScreen: (token: string, clientTimezone?: string) => {
    const params = clientTimezone
      ? `?client_timezone=${encodeURIComponent(clientTimezone)}`
      : "";
    return request<HomeScreen>(`/home${params}`, token);
  },
};
