import { KeyboardAvoidingView, Platform, StyleSheet, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { JobSearchSetupForm } from "@/features/job-search/components/JobSearchSetupForm";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useAuth } from "@/contexts/AuthContext";
import { useJobSearch } from "@/features/job-search/hooks/useJobSearch";
import { useTheme } from "@/lib/theme";

export default function MyJobSetupScreen() {
  const owner = useAccountViewOwner();
  return <MyJobSetupView key={owner.key} isCurrent={owner.isCurrent} />;
}

/** Multi-step job-search setup as a pushed screen (matches Learning create:
 *  multi-step forms are screens, short forms are sheets). */
function MyJobSetupView({ isCurrent }: { isCurrent: () => boolean }) {
  const { token } = useAuth();
  const { t } = useTranslation();
  const theme = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { dashboard, loading, busy, error, refresh, save } = useJobSearch(isCurrent);

  if (!token) return <Redirect href="/login" />;

  return (
    <View
      style={[
        styles.root,
        { backgroundColor: theme.bg, paddingTop: insets.top, paddingBottom: insets.bottom },
      ]}
    >
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        {loading && !dashboard.profile ? (
          <SkeletonList />
        ) : error && !dashboard.profile ? (
          <StateView
            variant="error"
            title={t("my_job.refresh_error")}
            onRetry={() => void refresh()}
          />
        ) : (
          <JobSearchSetupForm
            initial={dashboard.profile}
            busy={busy}
            onClose={() => router.back()}
            onSave={save}
          />
        )}
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  flex: { flex: 1 },
});
