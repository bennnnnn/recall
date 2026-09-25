import { Href, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";
import type { StyleProp, ViewStyle } from "react-native";

import { IconButton } from "./IconButton";
import { IconSize } from "@/lib/icons";
import { Space } from "@/lib/space";

type Props = {
  /** Where to go when there is no back stack (e.g. opened via deep link). */
  fallback?: Href;
  icon?: "chevron-back" | "arrow-back";
  style?: StyleProp<ViewStyle>;
};

export function StackBackButton({ fallback = "/", icon = "chevron-back", style }: Props) {
  const router = useRouter();
  const { t } = useTranslation();

  return (
    <IconButton
      name={icon}
      size={IconSize.lg}
      accessibilityLabel={t("common.back")}
      onPress={() => {
        if (router.canGoBack()) router.back();
        else router.replace(fallback);
      }}
      style={[{ marginLeft: Space.xxs }, style]}
    />
  );
}
