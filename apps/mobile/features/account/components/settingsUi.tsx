import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Animated, ScrollView, StyleSheet, View, type HostInstance } from "react-native";
import { type Href, Redirect, router } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import type { User } from "@/lib/api";
import { SettingsPinnedBar } from "@/features/account/components/SettingsPinnedBar";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import type { IconName } from "@/ui/icons/names";
import { ListGroup } from "@/ui/list/ListGroup";
import { ListRow } from "@/ui/list/ListRow";
import { confirmDialog, type ConfirmOptions } from "@/ui/overlay/dialogs";
import { SelectMenu, type SelectOption } from "@/ui/overlay/SelectMenu";

/**
 * The Settings kit: one page layout, one group and four rows, all drawn by
 * the app's ListRow and ListGroup. Every Settings screen builds from these.
 */

const layout = StyleSheet.create({
  section: { marginTop: Space.lg },
  content: { paddingHorizontal: Space.md, paddingTop: Space.xs },
});

/** Padding for a Settings list; FlashList pages pass it as contentContainerStyle. */
export function useSettingsContentStyle(options?: { underStatusBar?: boolean }) {
  const insets = useSafeAreaInsets();
  return [
    layout.content,
    options?.underStatusBar ? { paddingTop: insets.top + Space.md } : null,
    { paddingBottom: insets.bottom + Space.lg },
  ];
}

/**
 * A Settings page: sends a signed-out visitor to login, then scrolls its
 * groups with the shared padding. The page without a stack header (Settings
 * home) passes `ownBarTitle`: it starts under the status bar and keeps its own
 * Back on screen (SettingsPinnedBar).
 */
export function SettingsPage({
  children,
  ownBarTitle,
}: {
  children: ReactNode;
  ownBarTitle?: string;
}) {
  const { token } = useAuth();
  const theme = useTheme();
  const contentStyle = useSettingsContentStyle({ underStatusBar: ownBarTitle != null });
  const [scrollY] = useState(() => new Animated.Value(0));
  const onScroll = useMemo(
    () =>
      Animated.event([{ nativeEvent: { contentOffset: { y: scrollY } } }], { useNativeDriver: true }),
    [scrollY],
  );
  if (!token) return <Redirect href="/login" />;
  if (ownBarTitle == null) {
    return (
      <ScrollView
        keyboardShouldPersistTaps="handled"
        style={{ flex: 1, backgroundColor: theme.bg }}
        contentContainerStyle={contentStyle}
      >
        {children}
      </ScrollView>
    );
  }
  return (
    <View style={{ flex: 1, backgroundColor: theme.bg }}>
      <Animated.ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={contentStyle}
        onScroll={onScroll}
        scrollEventThrottle={16}
      >
        {children}
      </Animated.ScrollView>
      <SettingsPinnedBar title={ownBarTitle} scrollY={scrollY} />
    </View>
  );
}

/** Rows under an optional heading, a thin gap between each. */
export function SettingsGroup({ label, children }: { label?: string; children: ReactNode }) {
  return (
    <ListGroup label={label} spaced style={layout.section}>
      {children}
    </ListGroup>
  );
}

type RowBase = {
  title: string;
  subtitle?: string;
  value?: string;
  icon?: IconName;
  leading?: ReactNode;
  disabled?: boolean;
  busy?: boolean;
  accessibilityHint?: string;
};

function rowLabel(title: string, value?: string): string {
  return value ? `${title}, ${value}` : title;
}

/**
 * A row you tap. With `href` it opens that page and shows a chevron;
 * `onPress` still runs first (to prefetch, say). A row that navigates in
 * its own `onPress` passes `chevron`.
 */
export function SettingsLinkRow({
  href,
  chevron,
  onPress,
  danger,
  accent,
  ...row
}: RowBase & {
  href?: Href;
  chevron?: boolean;
  onPress?: () => void;
  danger?: boolean;
  accent?: boolean;
}) {
  return (
    <ListRow
      {...row}
      danger={danger}
      accent={accent}
      accessory={href || chevron ? "chevron" : undefined}
      accessibilityLabel={rowLabel(row.title, row.value)}
      onPress={() => {
        onPress?.();
        if (href) router.push(href);
      }}
    />
  );
}

/**
 * A row that shows a value. A long press (copying it, say) is offered to a screen reader
 * too, named by `longPressLabel`.
 */
export function SettingsValueRow({
  onLongPress,
  longPressLabel,
  ...row
}: Omit<RowBase, "disabled" | "busy" | "accessibilityHint"> & {
  onLongPress?: () => void;
  longPressLabel?: string;
}) {
  const actions = onLongPress && longPressLabel ? [{ name: "longpress", label: longPressLabel }] : undefined;
  return (
    <ListRow
      {...row}
      onLongPress={onLongPress}
      accessibilityActions={actions}
      onAccessibilityAction={actions ? () => onLongPress?.() : undefined}
    />
  );
}

/**
 * A switch. It moves when tapped and stays a switch while it saves: no spinner in its place,
 * and never held back because another setting is saving (``useSettingSave``). `disabled` is
 * only for a switch that cannot move, which its subtitle says why.
 */
export function SettingsSwitchRow({
  value,
  onValueChange,
  ...row
}: Omit<RowBase, "value" | "busy"> & { value: boolean; onValueChange: (next: boolean) => void }) {
  return <ListRow {...row} switchValue={value} onSwitchChange={onValueChange} />;
}

/**
 * Saves account settings from a switch or a menu: the new value shows at once, saves run in
 * the order they were made (``AuthContext.updateUser``), and a save that fails puts the old
 * value back and says so. Nothing waits on it, so a second tap is never lost.
 */
export function useSettingSave() {
  const { user, updateUser } = useAuth();
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  // The account by its id, not its token: a token refresh is the same account.
  const account = user?.id ?? null;
  const currentAccount = useRef(account);
  useEffect(() => {
    currentAccount.current = account;
    // Left (a page for another account replaces it): its late failure says nothing.
    return () => {
      currentAccount.current = null;
    };
  }, [account]);
  return useCallback(
    (patch: Partial<User>) => {
      const savedFor = currentAccount.current;
      // Named, not written in place: it is handed the failure (swallowedCatches.test.ts).
      const failed = () => {
        // A save from an account signed out since says nothing to the next one.
        if (savedFor && savedFor === currentAccount.current) {
          reportRecoverableError(feedback, t("common.error"));
        }
      };
      updateUser(patch).catch(failed);
    },
    [updateUser, feedback, t],
  );
}

/**
 * A row that opens its choices in a popover anchored to it (never inline;
 * see chat-ux-bans §13). It owns the open state.
 */
export function SettingsMenuRow<K extends string>({
  options,
  selectedKey,
  onSelect,
  ...row
}: RowBase & {
  options: readonly (SelectOption & { key: K })[];
  selectedKey: K;
  onSelect: (key: K) => void;
}) {
  const [open, setOpen] = useState(false);
  const rowRef = useRef<HostInstance>(null);
  return (
    <>
      <ListRow
        {...row}
        ref={rowRef}
        expanded={open}
        accessibilityLabel={rowLabel(row.title, row.value)}
        onPress={() => setOpen(true)}
      />
      <SelectMenu
        visible={open}
        anchorRef={rowRef}
        options={[...options]}
        selectedKey={selectedKey}
        disabled={row.disabled || row.busy}
        onClose={() => setOpen(false)}
        onSelect={(key) => {
          const option = options.find((candidate) => candidate.key === key);
          if (option) onSelect(option.key);
        }}
      />
    </>
  );
}

/**
 * Runs one Settings action at a time: asks first when given `confirm`,
 * marks which action is busy, and reports a failure without throwing.
 * Resolves true when the action ran and succeeded.
 */
export function useSettingsAction() {
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const [busy, setBusy] = useState<string | null>(null);
  const running = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const run = useCallback(
    async (
      key: string,
      action: () => Promise<unknown>,
      options?: { confirm?: ConfirmOptions; errorKey?: string },
    ): Promise<boolean> => {
      if (running.current) return false;
      if (options?.confirm && !(await confirmDialog(options.confirm))) return false;
      if (running.current || !mounted.current) return false;
      running.current = true;
      setBusy(key);
      try {
        await action();
        return true;
      } catch {
        if (mounted.current) reportRecoverableError(feedback, t(options?.errorKey ?? "common.error"));
        return false;
      } finally {
        running.current = false;
        if (mounted.current) setBusy(null);
      }
    },
    [feedback, t],
  );

  return { busy, run };
}
