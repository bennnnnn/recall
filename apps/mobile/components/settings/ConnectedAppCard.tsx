import type { ReactNode } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { SettingsGroup, type SettingsStyles } from "@/components/settings/settingsUi";
import { Space } from "@/lib/space";
import type { Theme } from "@/lib/theme";

export function ConnectedAppCard({
  title,
  description,
  value,
  leading,
  actionLabel,
  onAction,
  busy,
  disabled,
  children,
  styles,
  theme,
}: {
  title: string;
  description?: string;
  value?: string;
  leading: ReactNode;
  actionLabel: string;
  onAction: () => void;
  busy: boolean;
  disabled: boolean;
  children?: ReactNode;
  styles: SettingsStyles;
  theme: Theme;
}) {
  return (
    <SettingsGroup styles={styles}>
      <View style={[styles.menuRow, card.header]}>
        <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          {leading}
        </View>
        <View style={styles.rowBody}>
          <Text style={styles.rowTitle}>{title}</Text>
          {value ? <Text style={styles.meta}>{value}</Text> : null}
        </View>
        <Pressable
          onPress={onAction}
          disabled={disabled}
          accessibilityRole="button"
          accessibilityLabel={`${actionLabel} ${title}`}
          accessibilityState={{ disabled, busy }}
          style={({ pressed }) => [
            card.action,
            { backgroundColor: theme.bg },
            pressed && styles.rowPressed,
          ]}
        >
          {busy ? (
            <ActivityIndicator size="small" color={theme.primary} />
          ) : (
            <Text style={[styles.meta, card.actionText, { color: disabled ? theme.textSecondary : theme.text }]}>
              {actionLabel}
            </Text>
          )}
        </Pressable>
      </View>
      {description ? (
        <View style={[card.description, { backgroundColor: theme.settingsSurface }]}>
          <Text style={styles.meta}>{description}</Text>
        </View>
      ) : null}
      {children}
    </SettingsGroup>
  );
}

const card = StyleSheet.create({
  header: { gap: Space.sm },
  action: {
    minHeight: Space.minTouch,
    minWidth: Space.minTouch,
    maxWidth: "45%",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: Space.sm,
    paddingVertical: Space.xs,
    borderRadius: 24,
  },
  actionText: { fontWeight: "500", textAlign: "center" },
  description: { paddingHorizontal: Space.gutter, paddingBottom: Space.gutter },
});
