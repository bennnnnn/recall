import { useMemo, useRef, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Redirect, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { AuthScrollLayout } from "@/components/AuthScrollLayout";
import { Button } from "@/ui/controls/Button";
import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { FeatureShowcase, MAX_FONT_SCALE, SLIDES } from "@/features/auth/components/landing/FeatureShowcase";
import { offerPlansAfterSignIn } from "@/features/billing/model/welcomePlans";
import { tap } from "@/lib/haptics";
import { Space } from "@/lib/space";
import { BrandAccent } from "@/lib/accentRuntime";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

/** The landing: what Recall does, shown as it does it, before sign-in, in the brand's indigo.
 * Next turns the slides; Get started shows only on the last, so every slide is seen. */
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
  const [slide, setSlide] = useState(0);
  const onLast = slide >= SLIDES.length - 1;

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
      {/* Headline and slides stay together, centred: a tall screen or a tablet shows no gap. */}
      <AuthScrollLayout
        justify="center"
        footer={
          <Button
            title={onLast ? t("onboarding.get_started") : t("onboarding.next")}
            onPress={
              onLast
                ? () => void finish()
                : () => {
                    tap();
                    setSlide(slide + 1);
                  }
            }
            loading={finishing}
            loadingLabel={t("onboarding.get_started")}
            disabled={finishing}
            size="lg"
            style={s.cta}
          />
        }
      >
        {/* Balanced lines: no word left alone on the second (Android balances, iOS pushes out). */}
        <Text
          style={s.tagline}
          accessibilityRole="header"
          maxFontSizeMultiplier={MAX_FONT_SCALE}
          textBreakStrategy="balanced"
          lineBreakStrategyIOS="push-out"
        >
          {t("onboarding.headline")}
        </Text>

        <View style={s.showcase}>
          <FeatureShowcase index={slide} onIndexChange={setSlide} />
        </View>
      </AuthScrollLayout>
    </LinearGradient>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    root: { flex: 1 },
    tagline: {
      ...Type.title,
      ...Weight.semibold,
      color: theme.text,
      textAlign: "center",
      marginTop: Space.sm,
      paddingHorizontal: Space.sm,
    },
    showcase: { marginTop: Space.lg, marginBottom: Space.md },
    cta: { alignSelf: "stretch" },
  });
}
