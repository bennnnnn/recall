import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { selection } from "@/lib/haptics";
import { Theme, useTheme } from "@/lib/theme";

export type AttachmentSource = "camera" | "photo" | "file";

type Props = {
  visible: boolean;
  onClose: () => void;
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

/** Attach source picker (AppSheet — reliable over the chat drawer). */
export function AttachmentSourceSheet({ visible, onClose, onSelect }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);

  const pick = (source: AttachmentSource) => {
    selection();
    onSelect(source);
  };

  return (
    <AppSheet
      visible={visible}
      onClose={onClose}
      variant="bottom"
      withHandle
      minBottomPadding={24}
      contentContainerStyle={s.panel}
    >
      <SheetRow
        icon="camera-outline"
        label={t("chat.attach_camera")}
        onPress={() => pick("camera")}
        theme={theme}
        styles={s}
      />
      <SheetRow
        icon="images-outline"
        label={t("chat.attach_photo")}
        onPress={() => pick("photo")}
        theme={theme}
        styles={s}
        showDivider
      />
      <SheetRow
        icon="document-outline"
        label={t("chat.attach_file")}
        onPress={() => pick("file")}
        theme={theme}
        styles={s}
        showDivider
      />
    </AppSheet>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    panel: {
      backgroundColor: C.inputBg,
      borderTopLeftRadius: 20,
      borderTopRightRadius: 20,
      paddingBottom: 4,
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
