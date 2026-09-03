import { accountApi } from "@/lib/api/account";
import { analyticsApi } from "@/lib/api/analytics";
import { attachmentsApi } from "@/lib/api/attachments";
import { chatsApi } from "@/lib/api/chats";
import { discoverApi } from "@/lib/api/discover";
import { imagesApi } from "@/lib/api/images";
import { integrationsApi } from "@/lib/api/integrations";
import { memoriesApi } from "@/lib/api/memories";
import { projectsApi } from "@/lib/api/projects";
import { speechApi } from "@/lib/api/speech";
import { todosApi } from "@/lib/api/todos";

export type * from "@/lib/api/types";
export type { ProductEventName } from "@/lib/api/analytics";
export {
  attachmentRecordExists,
  type AttachmentListItem,
} from "@/lib/api/attachments";
export {
  loginWithApple,
  loginWithDev,
  loginWithGoogle,
  transcribeSpeech,
} from "@/lib/api/auth";
export { chatWebSocketUrl, checkHealth } from "@/lib/api/connectivity";
export {
  logoutSession,
  setTokenRefreshHandler,
  setUnauthorizedHandler,
} from "@/lib/api/client";

export const api = {
  ...accountApi,
  ...analyticsApi,
  ...chatsApi,
  ...memoriesApi,
  ...discoverApi,
  ...todosApi,
  ...projectsApi,
  ...integrationsApi,
  ...attachmentsApi,
  ...imagesApi,
  ...speechApi,
};
