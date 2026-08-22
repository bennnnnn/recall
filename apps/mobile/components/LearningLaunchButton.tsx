import { StyleSheet } from "react-native";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { Space } from "@/lib/space";
import type { LearningLaunchAction } from "@/lib/parseLearningLaunch";

type Props = {
  action?: LearningLaunchAction;
  onPress: () => void;
};

export function LearningLaunchButton({ action = "continue", onPress }: Props) {
  const { t } = useTranslation();
  return (
    <Button
      title={action === "start" ? t("lesson.start") : t("lesson.open")}
      onPress={onPress}
      style={styles.button}
      accessibilityLabel={action === "start" ? t("lesson.start") : t("lesson.open")}
    />
  );
}

const styles = StyleSheet.create({
  button: { marginTop: Space.sm },
});
