import { useAuth } from "@/contexts/AuthContext";
import { configurePurchases } from "@/features/billing/model/purchases";
import { api } from "@/lib/api";
import type { PaidPlanId } from "@/lib/plan";

export function useSubscriptionActions() {
  const { token, user, refreshUser, profileValidated } = useAuth();

  /** Ask the server to re-read the store; the plan only changes there. Both calls
   * return the account, shown as is (code-health audit NET-19). */
  const syncSubscription = async () => {
    if (!token) return false;
    await refreshUser(api.syncSubscription);
    return true;
  };

  const devUpgrade = async (plan: PaidPlanId) => {
    if (!token) return false;
    try {
      await refreshUser((current) => api.devUpgradePro(current, plan));
      return true;
    } catch {
      return false;
    }
  };

  /** The store is set up once the server confirms the account: read the account again when
   * it was never confirmed (a launch offline), else run the set-up again (one that hung). */
  const setUpStore = (): Promise<void> =>
    profileValidated && user ? configurePurchases(user.id) : refreshUser();

  return { token, user, syncSubscription, devUpgrade, setUpStore };
}
