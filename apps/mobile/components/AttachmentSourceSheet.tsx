import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";

export type AttachmentSource = "camera" | "photo" | "file";

type Props = {
  onSelect: (source: AttachmentSource) => void;
};

type RowProps = {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  onPress: () => void;
  theme: Theme;
  styles: ReturnType<typeof makeStyles>;
  showDivider?: boolean;
};

function SheetRow({ icon, label, onPress, theme, styles, showDivider }: RowProps) {
  return (
    <>
      {showDivider ? <View style={styles.divider} /> : null}
      <Pressable
        style={({ pressed }) => [styles.item, pressed && styles.itemPressed]}
        onPress={onPress}
      >
        <View style={styles.iconWrap}>
          <Ionicons name={icon} size={20} color={theme.primary} />
        </View>
        <Text style={styles.label}>{label}</Text>
      </Pressable>
    </>
  );
}

export function AttachmentSourceSheet({ onSelect }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={s.shadowWrap}>
      <View style={s.panel}>
        <SheetRow
          icon="camera-outline"
          label={t("chat.attach_camera")}
          onPress={() => onSelect("camera")}
          theme={theme}
          styles={s}
        />
        <SheetRow
          icon="images-outline"
          label={t("chat.attach_photo")}
          onPress={() => onSelect("photo")}
          theme={theme}
          styles={s}
          showDivider
        />
        <SheetRow
          icon="document-outline"
          label={t("chat.attach_file")}
          onPress={() => onSelect("file")}
          theme={theme}
          styles={s}
          showDivider
        />
      </View>
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    shadowWrap: {
      marginBottom: 0,
      borderRadius: 18,
      shadowColor: "#000",
      shadowOffset: { width: 0, height: 8 },
      shadowOpacity: C.isDark ? 0.45 : 0.16,
      shadowRadius: 16,
      elevation: 14,
    },
    panel: {
      backgroundColor: C.inputBg,
      borderRadius: 18,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.composerBorder,
      overflow: "hidden",
    },
    item: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: 14,
      paddingVertical: 13,
      gap: 12,
    },
    itemPressed: {
      backgroundColor: C.surfaceAlt,
    },
    iconWrap: {
      width: 36,
      height: 36,
      borderRadius: 10,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.primaryLight,
    },
    label: {
      fontSize: 16,
      color: C.text,
      fontWeight: "600",
      flex: 1,
    },
    divider: {
      height: StyleSheet.hairlineWidth,
      backgroundColor: C.border,
      marginLeft: 62,
    },
  });
}
