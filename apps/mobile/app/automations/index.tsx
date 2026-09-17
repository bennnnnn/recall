import { useCallback, useMemo, useState } from "react";
import { RefreshControl, StyleSheet, View } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { AddFab } from "@/components/AddFab";
import { AddAutomationSheet } from "@/components/automations/AddAutomationSheet";
import { AutomationCard } from "@/components/automations/AutomationCard";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { UpgradeSheet } from "@/components/UpgradeSheet";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useAuth } from "@/contexts/AuthContext";
import { useAutomationsList } from "@/hooks/useAutomationsList";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";

export default function AutomationsScreen() {
  const owner = useAccountViewOwner();
  return <AutomationsContent key={owner.key} isCurrent={owner.isCurrent} />;
}

function AutomationsContent({ isCurrent }: { isCurrent: () => boolean }) {
  const { token, user } = useAuth();
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const router = useRouter();
  const { automations, loading, error, creating, refresh, create } = useAutomationsList(isCurrent);
  const [pullRefreshing, setPullRefreshing] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const isPro = user?.plan === "pro";

  useFocusEffect(
    useCallback(() => {
      void refresh({ silent: true });
    }, [refresh]),
  );

  const openCreate = useCallback(() => {
    if (!isCurrent()) return;
    if (!isPro) {
      setUpgradeOpen(true);
      return;
    }
    setSheetOpen(true);
  }, [isCurrent, isPro]);

  const openAutomation = useCallback(
    (id: string) => {
      if (isCurrent()) router.push(`/automations/${id}`);
    },
    [router, isCurrent],
  );

  if (!token) return <Redirect href="/login" />;

  return (
    <View style={s.root}>
      {loading && automations.length === 0 && !error ? (
        <SkeletonList />
      ) : (
        <FlashList
          data={automations}
          keyExtractor={(item) => item.id}
          contentContainerStyle={s.content}
          ItemSeparatorComponent={() => <View style={s.listGap} />}
          refreshControl={
            <RefreshControl
              refreshing={pullRefreshing}
              onRefresh={async () => {
                if (!isCurrent()) return;
                setPullRefreshing(true);
                await refresh({ silent: true });
                if (isCurrent()) setPullRefreshing(false);
              }}
              tintColor={C.primary}
            />
          }
          ListHeaderComponent={
            <>
              {!error && automations.length === 0 ? (
                <StateView
                  variant="empty"
                  icon="flash-outline"
                  title={t("automations.empty_title")}
                />
              ) : null}
              {error ? (
                <StateView
                  variant="error"
                  title={t("common.error")}
                  onRetry={() => {
                    if (isCurrent()) void refresh();
                  }}
                  retryLabel={t("common.retry")}
                />
              ) : null}
            </>
          }
          renderItem={({ item }) => <AutomationCard automation={item} onOpen={openAutomation} />}
        />
      )}

      <AddFab onPress={openCreate} accessibilityLabel={t("automations.add_a11y")} />

      <AddAutomationSheet
        visible={sheetOpen}
        saving={creating}
        initial={null}
        onClose={() => {
          if (isCurrent()) setSheetOpen(false);
        }}
        onSave={(prompt, frequency, nextRunAt) =>
          void create({ prompt, frequency, nextRunAt: nextRunAt.toISOString() }, (created) => {
            if (!isCurrent()) return;
            setSheetOpen(false);
            router.push(`/automations/${created.id}`);
          })
        }
      />

      <UpgradeSheet
        visible={upgradeOpen}
        onClose={() => {
          if (isCurrent()) setUpgradeOpen(false);
        }}
        source="automations"
      />
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: C.bg },
    content: { padding: Space.md, paddingBottom: 96 },
    listGap: { height: Space.sm },
  });
}
