import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import type { PaidPlanId } from "@/lib/plan";

export function useSubscriptionActions() {
  const { token, user, refreshUser } = useAuth();

  /** Ask the server to re-read the store; the plan only changes there. */
  const syncSubscription = async () => {
    if (!token) return false;
    await api.syncSubscription(token);
    await refreshUser();
    return true;
  };

  const devUpgrade = async (plan: PaidPlanId) => {
    if (!token) return false;
    try {
      await api.devUpgradePro(token, plan);
      await refreshUser();
      return true;
    } catch {
      return false;
    }
  };

  return { token, user, syncSubscription, devUpgrade };
}
