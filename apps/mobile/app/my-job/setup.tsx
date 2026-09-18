import { ActivityIndicator, KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { JobSearchSetupForm } from "@/components/jobSearch/JobSearchSetupForm";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useAuth } from "@/contexts/AuthContext";
import { useJobSearch } from "@/hooks/useJobSearch";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

export default function MyJobSetupScreen() {
  const owner = useAccountViewOwner();
  return <MyJobSetupView key={owner.key} isCurrent={owner.isCurrent} />;
}

/** Multi-step job-search setup as a pushed screen (matches Learning create:
 *  multi-step forms are screens, short forms are sheets). */
function MyJobSetupView({ isCurrent }: { isCurrent: () => boolean }) {
  const { token } = useAuth();
  const theme = useTheme();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { dashboard, loading, busy, save } = useJobSearch(isCurrent);

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
          <View style={styles.loading}>
            <ActivityIndicator color={theme.primary} size="large" />
          </View>
        ) : (
          <ScrollView
            style={styles.flex}
            contentContainerStyle={styles.content}
            keyboardShouldPersistTaps="handled"
          >
            <JobSearchSetupForm
              initial={dashboard.profile}
              busy={busy}
              onClose={() => router.back()}
              onSave={save}
            />
          </ScrollView>
        )}
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  flex: { flex: 1 },
  loading: { flex: 1, alignItems: "center", justifyContent: "center" },
  content: { paddingBottom: Space.xl },
});
