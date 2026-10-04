import type { RefObject } from "react";
import { Pressable, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import { useTheme } from "@/lib/theme";

import { FieldLabel, useSetupStyles } from "./setupShared";
import { IconSize } from "@/ui/icons/sizes";

type Props = {
  /** The count and frequency rows the choice menus open from. */
  countRowRef: RefObject<View | null>;
  frequencyRowRef: RefObject<View | null>;
  count: 5 | 10 | 15;
  frequencyLabel: string;
  timeLabel: string;
  isPro: boolean;
  busy: boolean;
  onOpenCount: () => void;
  onOpenFrequency: () => void;
  onOpenDatePicker: () => void;
};

export function DeliveryStep({
  countRowRef,
  frequencyRowRef,
  count,
  frequencyLabel,
  timeLabel,
  isPro,
  busy,
  onOpenCount,
  onOpenFrequency,
  onOpenDatePicker,
}: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useSetupStyles();

  return (
    <>
      <View style={s.fieldGroup}>
        <FieldLabel>{t("my_job.count_label")}</FieldLabel>
        <Pressable
          ref={countRowRef}
          style={({ pressed }) => [
            s.selectRow,
            pressed && s.pressed,
            busy && s.disabled,
          ]}
          onPress={onOpenCount}
          disabled={busy}
          accessibilityRole="button"
        >
          <Text style={s.selectValue} numberOfLines={1}>
            {count} {t("my_job.count_jobs")}
          </Text>
          <Icon name="chevron-down" size={IconSize.sm} color={C.textTertiary} />
        </Pressable>
      </View>

      <View style={s.fieldGroup}>
        <FieldLabel>{t("my_job.frequency_label")}</FieldLabel>
        <Pressable
          ref={frequencyRowRef}
          style={({ pressed }) => [
            s.selectRow,
            pressed && s.pressed,
            busy && s.disabled,
          ]}
          onPress={onOpenFrequency}
          disabled={busy}
          accessibilityRole="button"
        >
          <Text style={s.selectValue} numberOfLines={1}>
            {frequencyLabel}
          </Text>
          <Icon name="chevron-down" size={IconSize.sm} color={C.textTertiary} />
        </Pressable>
        {!isPro ? (
          <Text style={s.helper}>{t("my_job.frequency_free_note")}</Text>
        ) : null}
      </View>

      <View style={s.fieldGroup}>
        <FieldLabel>{t("my_job.first_delivery_label")}</FieldLabel>
        <Pressable
          style={({ pressed }) => [s.dateCard, pressed && s.pressed]}
          onPress={onOpenDatePicker}
          disabled={busy}
          accessibilityRole="button"
        >
          <View style={s.dateIcon}>
            <Icon name="calendar" size={IconSize.md} color={C.primary} />
          </View>
          <View style={s.dateCopy}>
            <Text style={s.dateTitle}>{timeLabel}</Text>
            <Text style={s.dateMeta}>{t("my_job.first_delivery_meta")}</Text>
          </View>
          <Icon name="chevron-down" size={IconSize.sm} color={C.textTertiary} />
        </Pressable>
      </View>
    </>
  );
}
