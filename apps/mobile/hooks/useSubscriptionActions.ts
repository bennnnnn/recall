import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

export function useSubscriptionActions() {
  const { token, refreshUser } = useAuth();

  const syncSubscription = async () => {
    if (!token) return false;
    await api.syncSubscription(token);
    await refreshUser();
    return true;
  };

  const devUpgrade = async () => {
    if (!token) return false;
    try {
      await api.devUpgradePro(token);
      await refreshUser();
      return true;
    } catch {
      return false;
    }
  };

  return { token, syncSubscription, devUpgrade };
}
