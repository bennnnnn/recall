import { signOutGoogle } from "@/lib/google-auth";

/** Device/account side effects finish before another account signs in. Backend
 * session revocation is separate, so an offline server never holds logout UI. */
export async function clearSignedOutAccount(userId: string | undefined): Promise<void> {
  await Promise.allSettled([
    import("@/lib/downloadChatAttachment").then(({ clearLocalAttachmentFileCache }) => clearLocalAttachmentFileCache()),
    import("@/lib/todos/todoReminders").then(({ cancelAllTodoReminders }) => cancelAllTodoReminders()),
    import("@/lib/reminderPrefs").then(({ clearReminderLeadPrefs }) => clearReminderLeadPrefs()),
    import("@/lib/chatMessageCache").then(({ clearAllCachedChatMessages }) => clearAllCachedChatMessages()),
    import("@/lib/cache/memoryListCache").then(({ invalidateMemoriesCache }) => invalidateMemoriesCache()),
    import("@/lib/cache/galleryListCache").then(({ invalidateGalleryCache }) => invalidateGalleryCache()),
    import("@/lib/cache/integrationStatusCache").then(({ invalidateIntegrationStatusCache }) => invalidateIntegrationStatusCache()),
    import("@/lib/cache/suggestedRemindersCache").then(({ invalidateSuggestedRemindersCache }) => invalidateSuggestedRemindersCache()),
    import("@/lib/cache/chatListCache").then(({ invalidateChatListCache }) => invalidateChatListCache()),
    import("@/lib/cache/usageCache").then(({ invalidateUsageCache }) => invalidateUsageCache()),
    import("@/lib/purchases").then(({ signOutRevenueCat }) => signOutRevenueCat()),
    signOutGoogle(),
    ...(userId ? [
      import("@/lib/reminderSeen").then(({ clearSeenReminderIds }) => clearSeenReminderIds(userId)),
      import("@/lib/homeReminderNudges").then(({ clearHomeNudgeState }) => clearHomeNudgeState(userId)),
    ] : []),
  ]);
}
