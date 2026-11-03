import { useCallback } from "react";
import { useRouter } from "expo-router";

import { prefetchGallery } from "@/features/attachments/model/galleryListCache";
import { closeDrawer, startNewChatGlobal } from "@/features/chat/drawer/drawer";

/** Where the drawer's fixed buttons go: each closes the drawer first. */
export function useDrawerNavigation(token: string | null) {
  const router = useRouter();

  const newChat = useCallback(() => {
    closeDrawer();
    startNewChatGlobal();
  }, []);

  const openSettings = useCallback(() => {
    closeDrawer();
    router.push("/settings");
  }, [router]);

  const openReminders = useCallback(() => {
    closeDrawer();
    router.push("/todos");
  }, [router]);

  const openGallery = useCallback(() => {
    if (token) prefetchGallery(token);
    closeDrawer();
    router.push("/gallery");
  }, [router, token]);

  return { newChat, openSettings, openReminders, openGallery };
}
