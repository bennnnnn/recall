import { Href, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { IconButton } from "@/components/IconButton";
import { IconSize } from "@/lib/icons";

type Props = {
  /** Where to go when there is no back stack (e.g. opened via deep link). */
  fallback?: Href;
};

export function StackBackButton({ fallback = "/" }: Props) {
  const router = useRouter();
  const { t } = useTranslation();

  return (
    <IconButton
      name="chevron-back"
      size={IconSize.lg}
      accessibilityLabel={t("common.back")}
      onPress={() => {
        if (router.canGoBack()) router.back();
        else router.replace(fallback);
      }}
      style={{ marginLeft: 4 }}
    />
  );
}
