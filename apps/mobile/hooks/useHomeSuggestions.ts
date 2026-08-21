import { useAuthToken } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

export function useHomeSuggestions() {
  const token = useAuthToken();

  return {
    dismiss: async (suggestionId: string) => {
      if (!token) return false;
      try {
        await api.dismissSuggestion(token, suggestionId);
        return true;
      } catch {
        return false;
      }
    },
  };
}
