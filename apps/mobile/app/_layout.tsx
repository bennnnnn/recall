// First: crash reporting is on before any other app module runs (lib/sentryStart.ts).
import "@/lib/sentryStart";
import "@/lib/i18n";
// The caches that listen for app events as they load: loaded at launch, so a photo or chat
// deleted before any of them is first used still reaches their saved copies (metro.config.js
// loads every other import on first use; lib/__tests__/metroBundle.test.ts holds this list).
import "@/features/chat/model/messageCache";
import "@/features/chat/model/chatListCache";
import "@/features/attachments/model/galleryListCache";
import "@/features/memory/model/memoryListCache";
import "@/features/memory/model/memoryDocumentsCache";

import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { StyleSheet } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";

import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { AppStack } from "@/components/AppStack";
import { AiConsentRedirect } from "@/features/auth/components/AiConsentRedirect";
import { OpenedDocumentBootstrap } from "@/features/chat/components/OpenedDocumentBootstrap";
import { ChatGoneNotice } from "@/features/chat/components/ChatGoneNotice";
import { ActionFeedbackProvider } from "@/contexts/ActionFeedbackContext";
import { AppearanceProvider } from "@/contexts/AppearanceContext";
import { ModelsProvider } from "@/contexts/ModelsContext";
import { NetworkProvider, useNetwork } from "@/contexts/NetworkContext";
import { TodosProvider } from "@/features/todos/context/TodosContext";
import { PushNotificationBootstrap } from "@/features/todos/components/PushNotificationBootstrap";
import { OfflineFrame } from "@/components/OfflineBanner";
import { DialogHost } from "@/ui/overlay/DialogHost";
import { preloadFigures } from "@/components/rich/LazyHeavyRich";
import { useLaunchFonts } from "@/hooks/useLaunchFonts";
import { sweepOldPickerCopies } from "@/lib/accountFiles";
import { nameThisBuild } from "@/lib/api/appVersionHeader";
import { appVersion } from "@/lib/appVersion";
import { watchPhoneClock } from "@/lib/datetime/phoneClockSync";
import { boundImageMemoryCache } from "@/lib/images/memoryCache";
import { restoreLaunchPrefs } from "@/lib/launchPrefs";
import { markLaunchReady } from "@/lib/launchSplash";
import { LaunchReveal } from "@/components/LaunchReveal";
import { scheduleIdleTask } from "@/lib/scheduleIdle";
import { subscribeUnknownLatexCommands } from "@/lib/math/latexNames";
import { reportUnknownLatexCommandName } from "@/lib/sentry";
import { useTheme } from "@/lib/theme";

// Before the first render: the user's appearance, accent and language.
void restoreLaunchPrefs().then(() => markLaunchReady("prefs"));
// Before anything can be picked, so a fresh pick is never in the listing.
void sweepOldPickerCopies();
// Before the first picture decodes: the memory cache keeps what it decodes until told a limit.
boundImageMemoryCache();
// Before the first call: every call to the API names this build (lib/api/appVersionHeader.ts).
nameThisBuild(appVersion());

const markSessionRestored = () => markLaunchReady("session");

function RootNavigator() {
  const theme = useTheme();
  const { status } = useNetwork();
  const { token } = useAuth();

  return (
    <>
      <StatusBar style={theme.isDark ? "light" : "dark"} />
      {/* The banner takes its own room at the top; the screens sit below it, headers and all. */}
      <OfflineFrame status={status}>
        <AppStack signedIn={Boolean(token)} />
      </OfflineFrame>
    </>
  );
}

export default function RootLayout() {
  const fontsReady = useLaunchFonts();

  // Dates follow the phone's zone and 12/24-hour setting as they change.
  useEffect(() => watchPhoneClock(), []);

  // A LaTeX command a reply used that the renderer has no entry for: reported by name.
  useEffect(() => subscribeUnknownLatexCommands(reportUnknownLatexCommandName), []);

  // Work for later in the session, once the launch has settled.
  useEffect(() => {
    return scheduleIdleTask(() => {
      preloadFigures();
    });
  }, []);

  return (
    <GestureHandlerRootView style={styles.root}>
      <AppearanceProvider>
        <ActionFeedbackProvider>
          <AuthProvider onRestored={markSessionRestored}>
            {fontsReady ? (
              <ModelsProvider>
                <TodosProvider>
                  <NetworkProvider>
                    <PushNotificationBootstrap />
                    <OpenedDocumentBootstrap />
                    <ChatGoneNotice />
                    <AiConsentRedirect />
                    <RootNavigator />
                    <DialogHost />
                  </NetworkProvider>
                </TodosProvider>
              </ModelsProvider>
            ) : null}
          </AuthProvider>
        </ActionFeedbackProvider>
        <LaunchReveal />
      </AppearanceProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
});

/**
 * A crash no screen or section caught (the chat, the sign-in flow, or this
 * layout itself) shows the shared error view in place of the whole app.
 */
export { ScreenErrorBoundary as ErrorBoundary } from "@/components/ScreenErrorBoundary";
