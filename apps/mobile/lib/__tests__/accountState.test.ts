/**
 * Structural guard: after sign-out, the next account starts with nothing of the
 * previous one. Every module-level store (a top-level `let`, an empty `Map`/`Set`,
 * a resource cache, a value store or a cache file) is listed below under how it
 * keeps accounts apart. A new store fails this test until it is listed; a store
 * that can hold an account's data must be cleared in `lib/signOutCleanup.ts` (or
 * the sign-out in `contexts/AuthContext.tsx`), or be scoped to the session.
 */
import * as ts from "typescript";

declare const __dirname: string;

const ROOT = ts.sys.resolvePath(`${__dirname}/../..`);
const PRODUCTION_DIRS = ["app", "components", "contexts", "features", "hooks", "lib", "ui"];
const SIGN_OUT_FILES = ["lib/signOutCleanup.ts", "contexts/AuthContext.tsx"];

const STORE_PATTERNS = [
  /^(?:export )?let (\w+)/,
  /^(?:export )?const (\w+)(?:\s*:[^=]+)?\s*=\s*new (?:Map|Set|WeakMap|WeakSet)(?:<.*>)?\(\s*\)/,
  /^(?:export )?const (\w+)(?:\s*:[^=]+)?\s*=\s*new \w*ResourceCache\b/,
  /^(?:export )?const (\w+)(?:\s*:[^=]+)?\s*=\s*(?:createValueStore|cacheFile|createFilePref)\b/,
];

/** Holds an account's data; sign-out calls the named function. */
const CLEARED_AT_SIGN_OUT: Record<string, string> = {
  "features/attachments/model/attachmentStatusFile.ts#settledFile": "clearSettledStatuses",
  "features/speech/model/readAloudSession.ts#controls": "stopReadingAloud",
  "features/speech/model/readAloudSession.ts#readAloudSession": "stopReadingAloud",
  "features/speech/model/readAloudSession.ts#stopper": "stopReadingAloud",
  "features/attachments/model/downloadChatAttachment.ts#cacheGeneration": "clearLocalAttachmentFileCache",
  "features/attachments/model/downloadChatAttachment.ts#cacheRevision": "clearLocalAttachmentFileCache",
  "features/attachments/model/downloadChatAttachment.ts#cachedFiles": "clearLocalAttachmentFileCache",
  "features/attachments/model/downloadChatAttachment.ts#downloadRevisions": "clearLocalAttachmentFileCache",
  "features/attachments/model/downloadChatAttachment.ts#downloadsInFlight": "clearLocalAttachmentFileCache",
  "features/attachments/model/downloadChatAttachment.ts#localFileCache": "clearLocalAttachmentFileCache",
  "features/attachments/model/downloadChatAttachment.ts#refetch": "clearLocalAttachmentFileCache",
  "features/attachments/model/galleryListCache.ts#resource": "invalidateGalleryCache",
  // A file opened in Recall while an account was signed in goes with that account; one that came
  // while no one was signed in is no account's and waits for the next sign-in (openedDocument.ts).
  "features/attachments/model/openedDocument.ts#held": "clearOpenedDocument",
  "features/chat/model/chatListCache.ts#resource": "invalidateChatListCache",
  "features/chat/model/composerDraftFile.ts#draftsFile": "clearSavedComposerDrafts",
  "features/chat/model/padMathDrafts.ts#padMathTexts": "clearSavedComposerDrafts",
  "features/chat/model/draftLogic.ts#knownAssistantChats": "invalidateChatListCache",
  "features/chat/model/messageCache.ts#backgroundAt": "clearAllCachedChatMessages",
  "features/chat/model/messageCache.ts#cancelSave": "clearAllCachedChatMessages",
  "features/chat/model/messageCache.ts#chatClearGenerations": "clearAllCachedChatMessages",
  "features/chat/model/messageCache.ts#clearGeneration": "clearAllCachedChatMessages",
  "features/chat/model/messageCache.ts#diskWrites": "clearAllCachedChatMessages",
  "features/chat/model/messageCache.ts#keptPages": "clearAllCachedChatMessages",
  "features/chat/model/messageCache.ts#unsavedChats": "clearAllCachedChatMessages",
  "features/chat/model/quotaNudgeDismissal.ts#dismissedDate": "resetQuotaNudgeDismissal",
  "features/memory/model/memoryListCache.ts#resource": "invalidateMemoriesCache",
  "features/todos/model/reminderProposal.ts#savedHere": "clearSavedProposals",
  "features/todos/model/todoReminders.ts#pending": "cancelAllTodoReminders",
  "features/todos/model/todoReminders.ts#revision": "cancelAllTodoReminders",
  "features/todos/model/todoReminders.ts#scheduledVersions": "cancelAllTodoReminders",
  "lib/auth.ts#sessionAccessTokens": "clearToken",
  "lib/auth.ts#sessionGeneration": "clearToken",
  "lib/auth.ts#storageQueue": "clearToken",
  "features/chat/model/chatListFile.ts#chatListFile": "invalidateChatListCache",
  "lib/cache/usageCache.ts#resource": "invalidateUsageCache",
  "lib/cachedModels.ts#cachedModelsFile": "clearCachedModels",
  "lib/cachedUser.ts#cachedUserFile": "clearCachedUser",
  // Only whether a share is busy, but one the last account left hanging must not hold the next's.
  "lib/shareFile.ts#shareGeneration": "resetShareGuard",
  "lib/shareFile.ts#shareInFlight": "resetShareGuard",
  "lib/lesson/quizAttempts.ts#attempts": "clearQuizAttempts",
  "lib/linkPreview.ts#cache": "clearLinkPreviewCache",
  "lib/money/calculatorPositions.ts#positions": "clearCalculatorPositions",
  "lib/math/svgMath.ts#cache": "clearSvgMathCache",
  "lib/math/svgMath.ts#drawings": "clearSvgMathCache",
  "lib/onboarding.ts#onboardedPref": "clearOnboarded",
  "features/billing/model/purchases.ts#configuredAppUserId": "signOutRevenueCat",
  // A purchase held for approval, and Android's copy on disk: signOutRevenueCat releases both.
  "features/billing/model/heldPurchase.ts#held": "signOutRevenueCat",
  "features/billing/model/heldPurchase.ts#heldFile": "signOutRevenueCat",
  // Raised at sign-out, so a set-up still running for the account that left records nothing.
  "features/billing/model/purchases.ts#setupGeneration": "signOutRevenueCat",
  "features/billing/model/purchases.ts#storeSetUp": "signOutRevenueCat",
  "features/notifications/model/pushNotifications.ts#lastPushSync": "clearPushSyncRecord",
  // clearPushSyncRecord sets it back to false.
  "features/notifications/model/pushRegistration.ts#registered": "clearPushSyncRecord",
  "features/chat/model/streamingDraftStore.ts#draft": "publishStreamingDraft",
  "lib/syncRecords.ts#locationRecord": "forgetSyncRecords",
  "lib/syncRecords.ts#pushRecord": "forgetSyncRecords",
};

/** Read only by the sign-in session that wrote it (checked against `getSessionGeneration()` or keyed by it). */
const SCOPED_TO_SESSION = [
  "features/account/screens/NotificationsSettingsScreen.tsx#pending",
  "features/attachments/model/attachmentIndexStatus.ts#generation",
  "features/attachments/model/attachmentIndexStatus.ts#pollers",
  "features/attachments/model/attachmentIndexStatus.ts#settledLoad",
  "features/attachments/model/pendingComposerAttachment.ts#queued",
  // The sign-in the chat saw confirmed, read only while it is the session (cleared at sign-out too).
  "features/attachments/model/openedDocument.ts#confirmedSession",
  "features/chat/drawer/drawer.ts#chatMutationRevisions",
  "features/chat/drawer/drawer.ts#mutationSession",
  "features/chat/model/pageReads.ts#pageReads",
  "features/memory/hooks/useMemoryToggle.ts#pending",
  "features/memory/model/memoryDocumentsCache.ts#resource",
  "features/todos/model/todoMutationState.ts#current",
  "lib/api/client.ts#lastRefreshed",
  "lib/api/client.ts#refreshInFlight",
  "lib/api/client.ts#refreshRefused",
  "lib/api/client.ts#refreshRejected",
  "lib/api/client.ts#revalidated",
  "lib/productAnalytics.ts#waiting",
];

/** Work in progress for one chat, request or clip, keyed by ids another account never has. */
const IN_FLIGHT = [
  "features/account/model/profilePhoto.ts#generatedPhotos",
  "features/attachments/model/localAttachmentFile.ts#ownedCopies",
  "features/attachments/model/openedDocument.ts#copying",
  "features/chat/drawer/drawer.ts#_pendingTitleChatIds",
  "features/chat/model/draftLogic.ts#emptyChatChecks",
  "features/chat/model/latency.ts#pending",
  "features/chat/model/mutationLock.ts#pendingMutations",
  "features/chat/model/turnOutcome.ts#lastTokenAt",
  "features/chat/model/openedPage.ts#openReads",
  "features/chat/model/turnOutcome.ts#open",
  "features/chat/model/turnOutcome.ts#sendReadyMs",
  "features/chat/model/turnOutcome.ts#sampled",
  "features/chat/model/turnOutcome.ts#tool",
  "features/drafts/model/emailDraftFlush.ts#flushers",
  "features/speech/model/pronunciation.ts#backgroundStop",
  "features/speech/model/pronunciation.ts#cloudPlaybackFinish",
  "features/speech/model/pronunciation.ts#cloudPlayerCleanup",
  "features/speech/model/pronunciation.ts#speakGeneration",
  "features/speech/model/pronunciation.ts#ttsAbort",
  "features/speech/model/pronunciation.ts#ttsStartLoggedFor",
  "features/speech/model/pronunciation.ts#ttsTapAt",
  "features/speech/model/ttsClipFetch.ts#prefetch",
  // An ended session's logout still owed to the server, keyed by its own tokens; the next
  // account never reads it, and it must outlive the sign-out that wrote it.
  "lib/pendingLogout.ts#hasPending",
  "lib/pendingLogout.ts#retrying",
  "lib/pendingLogout.ts#storage",
];

/** No account data: phone settings, native modules, players, listeners, counters, lookup tables. */
const NO_ACCOUNT_DATA = [
  "components/LaunchReveal.tsx#played",
  "components/CodeBlock.tsx#cachedTokenizer",
  "components/CodeBlock.tsx#tokenStyles",
  "components/rich/LazyHeavyRich.tsx#simulationSizing",
  "components/rich/LazyHeavyRich.tsx#simulationSizingLoad",
  // Each canvas font's digit widths, a property of the face.
  "components/rich/skia/fontRuns.ts#digitCells",
  "components/markdown/LinkPreviewTrust.tsx#NO_PREVIEWS",
  "features/attachments/model/attachmentIndexStatus.ts#offline",
  "features/attachments/model/attachmentIndexStatus.ts#stopWatchingNetwork",
  "features/attachments/model/attachments.ts#nativePickerActive",
  "features/attachments/model/attachments.ts#nativePickerGeneration",
  "features/attachments/model/downloadChatAttachment.ts#swept",
  "features/attachments/model/galleryLayout.ts#layoutPref",
  // How many opened files were taken: a copy a newer one overtook gives way.
  "features/attachments/model/openedDocument.ts#claims",
  // The plans offers' read-and-write queue: the offers file is the phone's, not an account's.
  "features/billing/model/welcomePlans.ts#pending",
  "features/chat/drawer/drawer.ts#_onTitlePendingChange",
  "features/chat/hooks/useMathKeyboardInsert.ts#lastSystemKeyboardHeight",
  "features/chat/model/messageCache.ts#swept",
  "features/home/model/homeOnScreen.ts#homeOnScreen",
  "features/images/components/dotField.ts#compiled",
  // The calls holding the phone's one audio route, counted so a stale hang-up keeps the live one's.
  "features/speech/model/callAudio.ts#holders",
  "features/speech/model/liveTalkSfx.ts#cueEpoch",
  "features/speech/model/liveTalkSfx.ts#cuePlayer",
  "features/speech/model/pronunciation.ts#speechModule",
  "features/speech/model/readAloudSession.ts#chunk",
  "features/speech/model/readAloudSession.ts#clipMs",
  "features/speech/model/readAloudSession.ts#heardClipsMs",
  "features/speech/model/readAloudSession.ts#lastId",
  "features/speech/model/speechRate.ts#ratePref",
  "features/speech/model/ttsPreference.ts#ttsModelPref",
  "features/todos/model/optimisticTodo.ts#optimisticTodoSeq",
  "features/todos/model/reminderAlerts.ts#toldAlertsOff",
  "lib/accentPrefs.ts#accentPref",
  "lib/accentRuntime.ts#accent",
  "lib/api/client.ts#onTokenRefresh",
  "lib/api/client.ts#onUnauthorized",
  "lib/api/consentRefusal.ts#onConsentRequired",
  "lib/appearancePrefs.ts#appearancePref",
  "lib/appearanceRuntime.ts#preference",
  "lib/apple-auth.ts#appleModule",
  "lib/clockTick.ts#intervalId",
  "lib/clockTick.ts#listeners",
  "lib/datetime/format.ts#formatters",
  "lib/datetime/format.ts#phoneClock",
  "lib/datetime/format.ts#wallClockFormatters",
  "lib/datetime/phoneClock.ts#localization",
  "lib/fenceRegistry.ts#BY_ID",
  "lib/fenceRegistry.ts#BY_LANG",
  "lib/foregroundRefresh.ts#away",
  "lib/foregroundRefresh.ts#listeners",
  "lib/foregroundRefresh.ts#subscription",
  "lib/google-auth.ts#configured",
  "lib/google-auth.ts#googleModule",
  "lib/haptics.ts#enabled",
  "lib/hapticsPrefs.ts#hapticsPref",
  "lib/launchSplash.ts#deadlinePassed",
  "lib/launchSplash.ts#exited",
  "lib/launchSplash.ts#hidden",
  "lib/launchSplash.ts#ready",
  // How many previews are loading, and a counter raised at sign-out (waiting ones never go).
  "lib/linkPreview.ts#generation",
  "lib/linkPreview.ts#inFlight",
  "lib/math/svgMath.ts#rendererImpl",
  "lib/math/svgMath.ts#rendererPromise",
  "lib/preview/previewPageFile.ts#pageFiles",
  "lib/networkProbe.ts#netInfoConfigured",
  "lib/productAnalytics.ts#flushOnBackground",
  "lib/productAnalytics.ts#flushTimer",
  "features/billing/model/purchases.ts#purchasesModule",
  "features/notifications/model/pushNotifications.ts#androidChannelReady",
  "features/notifications/model/pushNotifications.ts#pushTokenFailureReported",
  "lib/reconnectRefresh.ts#lostAt",
  "lib/reduceMotion.ts#knownReduceMotion",
  "features/scanner/model/switchCue.ts#activePlayer",
  "features/scanner/model/switchCue.ts#cueEpoch",
  "features/scanner/model/switchCue.ts#releaseTimer",
  "lib/sentry.ts#sdk",
  "lib/sentry.ts#starting",
  "lib/skiaAvailability.ts#cached",
  "lib/speech/voiceAudio.ts#audioModule",
  "lib/speech/voiceAudio.ts#exclusiveMicStop",
  "lib/theme.ts#accented",
  "lib/webView.ts#cachedPreviewWebView",
  "lib/webViewMountQueue.ts#grantedTickets",
  "lib/webViewMountQueue.ts#listeners",
  "lib/webViewMountQueue.ts#nextTicketId",
  "lib/zoneReport.ts#inFlight",
  "ui/overlay/dialogs.ts#host",
];

function productionFiles(): string[] {
  return PRODUCTION_DIRS.flatMap((dir) =>
    ts.sys.readDirectory(`${ROOT}/${dir}`, [".ts", ".tsx"], ["**/__tests__/**", "**/vendor/**"]),
  ).filter((file) => !file.endsWith(".d.ts"));
}

function moduleStores(): string[] {
  const stores: string[] = [];
  for (const file of productionFiles()) {
    const relative = file.slice(ROOT.length + 1);
    for (const line of (ts.sys.readFile(file) ?? "").split("\n")) {
      const name = STORE_PATTERNS.map((pattern) => line.match(pattern)?.[1]).find(Boolean);
      if (name) stores.push(`${relative}#${name}`);
    }
  }
  return stores.sort();
}

const listed = [
  ...Object.keys(CLEARED_AT_SIGN_OUT),
  ...SCOPED_TO_SESSION,
  ...IN_FLIGHT,
  ...NO_ACCOUNT_DATA,
];

it("lists every module-level store under how it keeps accounts apart", () => {
  const found = moduleStores();
  const unlisted = found.filter((store) => !listed.includes(store));
  expect({ unlisted, stale: listed.filter((store) => !found.includes(store)) }).toEqual({
    unlisted: [],
    stale: [],
  });
});

it("lists each store once", () => {
  expect(listed.filter((store, index) => listed.indexOf(store) !== index)).toEqual([]);
});

/**
 * Native caches the store scan cannot see: expo-image keeps what it draws on disk (an
 * account's photos, avatar, chat images) unless told otherwise, so any use of it needs
 * its cache cleared at sign-out and sign-in.
 */
const NATIVE_CACHES = [{ keeps: /from "expo-image"/, clear: "clearImageCaches" }];

it("clears every native cache a view keeps an account's pictures in, at sign-out and sign-in", () => {
  const sources = productionFiles().map((file) => ts.sys.readFile(file) ?? "");
  const kept = NATIVE_CACHES.filter(({ keeps }) => sources.some((text) => keeps.test(text)));
  const missing = kept.flatMap(({ clear }) => {
    const calls = new RegExp(`\\b${clear}\\(`);
    return SIGN_OUT_FILES.filter((file) => !calls.test(ts.sys.readFile(`${ROOT}/${file}`) ?? ""))
      .map((file) => `${file}: ${clear}`);
  });
  expect(missing).toEqual([]);
});

it("calls each store's clear function on sign-out", () => {
  const signOut = SIGN_OUT_FILES.map((file) => ts.sys.readFile(`${ROOT}/${file}`) ?? "").join("\n");
  const missing = [...new Set(Object.values(CLEARED_AT_SIGN_OUT))].filter(
    (clear) => !new RegExp(`\\b${clear}\\(`).test(signOut),
  );
  expect(missing).toEqual([]);
});
