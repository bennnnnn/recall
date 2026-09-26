import { useCallback, useRef, useState } from "react";
import { Platform } from "react-native";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/contexts/AuthContext";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { formatAppleSignInError } from "@/lib/apple-auth";
import { isGoogleSignInConfigured, isGoogleWebClientConfigured } from "@/lib/config";
import { formatGoogleSignInError, isExpoGo } from "@/lib/google-auth";
import { tap } from "@/lib/haptics";
import { alertDialog } from "@/ui/overlay/dialogs";

export type LoginProvider = "apple" | "google" | "dev";

export function useLoginActions() {
  const { signInWithApple, signInWithGoogle, signInWithDev } = useAuth();
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const busyRef = useRef(false);
  const [busyProvider, setBusyProvider] = useState<LoginProvider | null>(null);

  const showSignInError = useCallback(
    (message: string) => {
      if (feedback) feedback.error(message);
      else void alertDialog({ title: t("login.sign_in_failed"), message });
    },
    [feedback, t],
  );

  const signInErrorMessage = useCallback(
    (error: unknown, provider: Exclude<LoginProvider, "dev">) => {
      const key =
        provider === "google"
          ? formatGoogleSignInError(error)
          : formatAppleSignInError(error);
      if (key === "cancelled") return null;
      if (key === "bundle_load_failed") return t("login.error_bundle");
      if (key === "native_module_missing") return t("login.error_native_module");
      if (key === "not_configured") return t("login.error_not_configured");
      if (key === "android_oauth_setup") return t("login.error_android_google");
      if (key === "generic") return t("login.error_generic");
      return key;
    },
    [t],
  );

  const handleApple = useCallback(async () => {
    if (busyRef.current) return;
    tap();
    busyRef.current = true;
    setBusyProvider("apple");
    try {
      await signInWithApple();
    } catch (error) {
      const message = signInErrorMessage(error, "apple");
      if (message) showSignInError(message);
    } finally {
      busyRef.current = false;
      setBusyProvider(null);
    }
  }, [showSignInError, signInErrorMessage, signInWithApple]);

  const handleGoogle = useCallback(async () => {
    if (busyRef.current) return;
    tap();
    if (isExpoGo()) {
      void alertDialog({
        title: t("login.google_unavailable_title"),
        message: t("login.google_unavailable_body"),
      });
      return;
    }
    if (!isGoogleWebClientConfigured()) {
      showSignInError(t("login.error_not_configured"));
      return;
    }
    if (Platform.OS === "ios" && !isGoogleSignInConfigured()) {
      showSignInError(t("login.error_not_configured"));
      return;
    }
    busyRef.current = true;
    setBusyProvider("google");
    try {
      await signInWithGoogle();
    } catch (error) {
      const message = signInErrorMessage(error, "google");
      if (message) showSignInError(message);
    } finally {
      busyRef.current = false;
      setBusyProvider(null);
    }
  }, [showSignInError, signInErrorMessage, signInWithGoogle, t]);

  const handleDev = useCallback(async () => {
    if (busyRef.current) return;
    tap();
    busyRef.current = true;
    setBusyProvider("dev");
    try {
      await signInWithDev();
    } catch (error) {
      showSignInError(
        error instanceof Error ? error.message : t("login.error_generic"),
      );
    } finally {
      busyRef.current = false;
      setBusyProvider(null);
    }
  }, [showSignInError, signInWithDev, t]);

  return {
    busyProvider,
    busy: busyProvider !== null,
    handleApple,
    handleGoogle,
    handleDev,
  };
}
