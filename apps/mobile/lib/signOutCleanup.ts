import { resetComposerDraftsForAccount } from "@/lib/chat/composerDraftReset";
import { signOutGoogle } from "@/lib/google-auth";

/** Device/account side effects finish before another account signs in. Backend
 * session revocation is separate, so an offline server never holds logout UI. */
export async function clearSignedOutAccount(userId: string | undefined): Promise<void> {
  resetComposerDraftsForAccount();
  await Promise.allSettled([
    import("@/features/attachments/model/downloadChatAttachment").then(({ clearLocalAttachmentFileCache }) => clearLocalAttachmentFileCache()),
    import("@/features/todos/model/todoReminders").then(({ cancelAllTodoReminders }) => cancelAllTodoReminders()),
    import("@/features/todos/model/reminderPrefs").then(({ clearReminderLeadPrefs }) => clearReminderLeadPrefs()),
    import("@/lib/chat/messageCache").then(({ clearAllCachedChatMessages }) => clearAllCachedChatMessages()),
    import("@/features/memory/model/memoryListCache").then(({ invalidateMemoriesCache }) => invalidateMemoriesCache()),
    import("@/features/attachments/model/galleryListCache").then(({ invalidateGalleryCache }) => invalidateGalleryCache()),
    import("@/features/integrations/model/integrationStatusCache").then(({ invalidateIntegrationStatusCache }) => invalidateIntegrationStatusCache()),
    import("@/lib/cache/suggestedRemindersCache").then(({ invalidateSuggestedRemindersCache }) => invalidateSuggestedRemindersCache()),
    import("@/lib/cache/chatListCache").then(({ invalidateChatListCache }) => invalidateChatListCache()),
    import("@/lib/cache/usageCache").then(({ invalidateUsageCache }) => invalidateUsageCache()),
    import("@/lib/purchases").then(({ signOutRevenueCat }) => signOutRevenueCat()),
    signOutGoogle(),
    ...(userId ? [
      import("@/features/todos/model/reminderSeen").then(({ clearSeenReminderIds }) => clearSeenReminderIds(userId)),
      import("@/features/todos/model/homeReminderNudges").then(({ clearHomeNudgeState }) => clearHomeNudgeState(userId)),
    ] : []),
  ]);
}
