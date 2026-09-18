import { useCallback, useMemo, useRef, useState } from "react";
import { Alert, Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { AddAutomationSheet } from "@/components/automations/AddAutomationSheet";
import { AutomationActionsSheet } from "@/components/automations/AutomationActionsSheet";
import { AutomationCard } from "@/components/automations/AutomationCard";
import { Icon } from "@/components/Icon";
import { SkeletonList } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAccountViewOwner } from "@/hooks/useAccountViewOwner";
import { useAuth } from "@/contexts/AuthContext";
import { useAutomationsList } from "@/hooks/useAutomationsList";
import type { Automation } from "@/lib/api";
import { shareAutomation } from "@/lib/automations/schedule";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export default function AutomationsScreen() {
  const owner = useAccountViewOwner();
  return <AutomationsContent key={owner.key} isCurrent={owner.isCurrent} />;
}

// Creation stays chat-based. The bottom entry bar mirrors ChatGPT Tasks and
// returns the user to chat instead of adding a second automation composer.
function AutomationsContent({ isCurrent }: { isCurrent: () => boolean }) {
  const { token } = useAuth();
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const insets = useSafeAreaInsets();
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

  if (!token) return <Redirect href="/login" />;

  const createBarBottom = Math.max(insets.bottom, 12) + Space.xs;
  const listBottomPadding = createBarBottom + 88;

  return (
    <View style={s.root}>
      {loading && automations.length === 0 && !error ? (
        <SkeletonList />
      ) : (
        <FlashList
          data={automations}
          keyExtractor={(item) => item.id}
          contentContainerStyle={{
            paddingHorizontal: Space.md,
            paddingTop: Space.lg,
            paddingBottom: listBottomPadding,
          }}
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
                  message={t("automations.empty_message")}
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

      <Pressable
        style={({ pressed }) => [
          s.createBar,
          {
            left: Space.md + insets.left,
            right: Space.md + insets.right,
            bottom: createBarBottom,
          },
          pressed && s.createBarPressed,
        ]}
        onPress={() => router.push("/")}
        accessibilityRole="button"
        accessibilityLabel="Create a task"
      >
        <Text style={s.createBarText}>Create a task</Text>
        <Icon name="mic-outline" size={24} color={C.textSecondary} />
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
                prompt: editTarget.prompt,
                frequency: editTarget.frequency,
                nextRunAt: new Date(editTarget.next_run_at),
              }
            : null
        }
        onClose={() => {
          if (isCurrent()) setEditTarget(null);
        }}
        onSave={(prompt, frequency, nextRunAt) => {
          const target = editTarget;
          setEditTarget(null);
          if (target) {
            void update(target.id, { prompt, frequency, next_run_at: nextRunAt.toISOString() });
          }
        }}
      />
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: C.bg },
    listGap: { height: Space.md },
    createBar: {
      position: "absolute",
      zIndex: 30,
      minHeight: 64,
      borderRadius: Radius.full,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      backgroundColor: C.surface,
      paddingLeft: Space.lg,
      paddingRight: Space.md,
      flexDirection: "row",
      alignItems: "center",
      gap: Space.md,
    },
    createBarPressed: { opacity: 0.72 },
    createBarText: {
      ...Type.body,
      fontSize: 18,
      lineHeight: 24,
      color: C.textSecondary,
      flex: 1,
    },
  });
}
