import { useCallback, useMemo, useRef, useState } from "react";
import { Alert, Pressable, RefreshControl, Text, View } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { AddAutomationSheet } from "@/components/automations/AddAutomationSheet";
import { AutomationActionsSheet } from "@/components/automations/AutomationActionsSheet";
import { AutomationCard } from "@/components/automations/AutomationCard";
import { Icon } from "@/components/Icon";
import { makeAutomationsStyles } from "@/components/automations/automationsStyles";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useAuth } from "@/contexts/AuthContext";
import { useAutomationsList } from "@/hooks/useAutomationsList";
import type { Automation } from "@/lib/api";
import { shareAutomation } from "@/lib/automations/schedule";
import { tap } from "@/lib/haptics";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useTheme } from "@/lib/theme";

export default function AutomationsScreen() {
  const owner = useAccountViewOwner();
  return <AutomationsContent key={owner.key} isCurrent={owner.isCurrent} />;
}

function AutomationsContent({ isCurrent }: { isCurrent: () => boolean }) {
  const { token } = useAuth();
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const C = useTheme();
  const s = useMemo(() => makeAutomationsStyles(C), [C]);
  const router = useRouter();
  const { automations, loading, error, refresh, update, remove } = useAutomationsList(isCurrent);
  const [pullRefreshing, setPullRefreshing] = useState(false);
  const [actionsTarget, setActionsTarget] = useState<Automation | null>(null);
  const [editTarget, setEditTarget] = useState<Automation | null>(null);
  const sharing = useRef(false);

  useFocusEffect(
    useCallback(() => {
      void refresh({ silent: true });
    }, [refresh]),
  );

  const openAutomation = useCallback(
    (id: string) => {
      if (isCurrent()) router.push(`/automations/${id}`);
    },
    [router, isCurrent],
  );

  const confirmDelete = useCallback(
    (automation: Automation) => {
      setActionsTarget(null);
      Alert.alert(
        t("automations.delete_confirm_title"),
        t("automations.delete_confirm_body"),
        [
          { text: t("common.cancel"), style: "cancel" },
          {
            text: t("common.delete"),
            style: "destructive",
            onPress: () => void remove(automation.id),
          },
        ],
      );
    },
    [t, remove],
  );

  const navigateToCreateTask = useCallback(() => {
    tap();
    router.push({ pathname: "/", params: { prefill: t("automations.create_prefill") } });
  }, [router, t]);

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
          renderItem={({ item }) => (
            <AutomationCard automation={item} onOpen={openAutomation} onLongPress={setActionsTarget} />
          )}
        />
      )}

      {/* Bottom "Create a task" bar */}
      <Pressable style={s.createBar} onPress={navigateToCreateTask} accessibilityRole="button">
        <Text style={s.createBarText}>{t("automations.create_bar")}</Text>
        <Icon name="mic-outline" size={20} color={C.textTertiary} style={s.createBarIcon} />
      </Pressable>

      <AutomationActionsSheet
        visible={!!actionsTarget}
        status={actionsTarget?.status ?? "active"}
        onClose={() => {
          if (isCurrent()) setActionsTarget(null);
        }}
        onEdit={() => {
          const target = actionsTarget;
          setActionsTarget(null);
          if (target) setEditTarget(target);
        }}
        onShare={() => {
          if (sharing.current || !actionsTarget) return;
          sharing.current = true;
          void shareAutomation(actionsTarget, t)
            .catch(() => {
              if (isCurrent()) reportRecoverableError(feedback, t("automations.share_failed"));
            })
            .finally(() => {
              sharing.current = false;
              if (isCurrent()) setActionsTarget(null);
            });
        }}
        onTogglePause={() => {
          const target = actionsTarget;
          setActionsTarget(null);
          if (target) void update(target.id, { status: target.status === "paused" ? "active" : "paused" });
        }}
        onDelete={() => {
          if (actionsTarget) confirmDelete(actionsTarget);
        }}
      />

      <AddAutomationSheet
        visible={!!editTarget}
        saving={false}
        initial={
          editTarget
            ? {
                title: editTarget.title,
                prompt: editTarget.prompt,
                frequency: editTarget.frequency,
                nextRunAt: new Date(editTarget.next_run_at),
              }
            : null
        }
        onClose={() => {
          if (isCurrent()) setEditTarget(null);
        }}
        onSave={(title, prompt, frequency, nextRunAt) => {
          const target = editTarget;
          setEditTarget(null);
          if (target) {
            void update(target.id, { title, prompt, frequency, next_run_at: nextRunAt.toISOString() });
          }
        }}
      />
    </View>
  );
}
