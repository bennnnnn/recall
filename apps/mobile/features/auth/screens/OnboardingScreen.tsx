import { useMemo, useRef, useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Redirect, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { AuthScrollLayout } from "@/components/AuthScrollLayout";
import { Button } from "@/ui/controls/Button";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { FeatureShowcase } from "@/features/auth/components/landing/FeatureShowcase";
import { offerPlansAfterSignIn } from "@/features/billing/model/welcomePlans";
import { tap } from "@/lib/haptics";
import { Space } from "@/lib/space";
import { BrandAccent } from "@/lib/accentRuntime";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Radius } from "@/lib/radius";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

const APP_ICON = require("@/assets/images/icon.png");

/** The landing: what Recall does, shown as it does it, before sign-in, in the brand's indigo. */
export default function Onboarding() {
  return (
    <BrandAccent>
      <Landing />
    </BrandAccent>
  );
}

function Landing() {
  const { onboarded, completeOnboarding } = useAuth();
  const router = useRouter();
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const feedback = useActionFeedbackOptional();
  const [finishing, setFinishing] = useState(false);
  const finishingRef = useRef(false);

  if (onboarded) return <Redirect href="/login" />;

  const gradientColors = [theme.primaryLight, theme.bg] as const;

  const finish = async () => {
    if (finishingRef.current) return;
    tap();
    finishingRef.current = true;
    setFinishing(true);
    try {
      // A first visit sees the plans once after it signs in; it can keep Free.
      await Promise.all([completeOnboarding(), offerPlansAfterSignIn()]);
      router.replace("/login");
    } catch {
      reportRecoverableError(feedback, t("common.error"));
    } finally {
      finishingRef.current = false;
      setFinishing(false);
    }
  };

  return (
    <LinearGradient colors={gradientColors} style={s.root}>
      <AuthScrollLayout
        justify="space-between"
        footer={
          <Button
            title={t("onboarding.get_started")}
            onPress={() => void finish()}
            loading={finishing}
            loadingLabel={t("onboarding.get_started")}
            disabled={finishing}
            size="lg"
            style={s.cta}
          />
        }
      >
        <View>
          <View style={s.brand}>
            <Image source={APP_ICON} style={s.icon} accessibilityIgnoresInvertColors />
            <Text style={s.name} accessibilityRole="header">{t("app.name")}</Text>
          </View>
          <Text style={s.tagline}>{t("onboarding.tagline")}</Text>
        </View>

        <View style={s.showcase}>
          <FeatureShowcase />
        </View>
      </AuthScrollLayout>
    </LinearGradient>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    root: { flex: 1 },
    brand: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: Space.xs,
      paddingTop: Space.sm,
    },
    icon: { width: 32, height: 32, borderRadius: Radius.md },
    name: { ...Type.title, ...Weight.bold, color: theme.text },
    tagline: {
      ...Type.title,
      ...Weight.semibold,
      color: theme.text,
      textAlign: "center",
      marginTop: Space.md,
      paddingHorizontal: Space.sm,
    },
    showcase: { marginVertical: Space.md },
    cta: { alignSelf: "stretch" },
  });
}
