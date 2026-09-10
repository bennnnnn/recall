import { useMemo } from "react";
import { ScrollView, Share, View } from "react-native";
import Constants from "expo-constants";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import {
  makeSettingsStyles,
  SettingsGroup,
  SettingsLinkRow,
} from "@/components/settings/settingsUi";
import { useAuth } from "@/contexts/AuthContext";
import { useModels } from "@/hooks/useModels";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";

export default function HelpSettingsScreen() {
  const { user } = useAuth();
  const { isPro } = useModels();
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeSettingsStyles(theme), [theme]);
  const insets = useSafeAreaInsets();
  const version = Constants.expoConfig?.version ?? "1.0.0";

  const shareFeedback = (kind: "problem" | "feedback") => {
    const plan = isPro ? t("settings.account_pro") : t("settings.account_free");
    const title =
      kind === "problem" ? t("settings.report_problem") : t("settings.send_feedback");
    const body = [
      title,
      "",
      `${t("settings.about_version")}: ${version}`,
      `${t("settings.plan_label")}: ${plan}`,
      `${t("settings.language")}: ${user?.locale ?? "en"}`,
    ].join("\n");
    void Share.share({ title, message: body });
  };

  return (
    <ScrollView
      style={s.scroll}
      contentContainerStyle={[s.content, { paddingBottom: insets.bottom + Space.lg }]}
    >
      <SettingsGroup styles={s}>
        <SettingsLinkRow
          title={t("settings.report_problem")}
          onPress={() => shareFeedback("problem")}
          styles={s}
          theme={theme}
        />
        <View style={s.menuSeparator} />
        <SettingsLinkRow
          title={t("settings.send_feedback")}
          onPress={() => shareFeedback("feedback")}
          styles={s}
          theme={theme}
        />
      </SettingsGroup>
    </ScrollView>
  );
}
