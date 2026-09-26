import { Href, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";
import type { StyleProp, ViewStyle } from "react-native";

import { HeaderButton } from "./HeaderButton";

type Props = {
  /** Where to go when there is no back stack (e.g. opened via deep link). */
  fallback?: Href;
  style?: StyleProp<ViewStyle>;
};

/** Back arrow in a round plate, for every stack header. */
export function StackBackButton({ fallback = "/", style }: Props) {
  const router = useRouter();
  const { t } = useTranslation();

  return (
    <HeaderButton
      icon="arrow-left"
      accessibilityLabel={t("common.back")}
      onPress={() => {
        if (router.canGoBack()) router.back();
        else router.replace(fallback);
      }}
      style={style}
      testID="stack-back"
    />
  );
}
