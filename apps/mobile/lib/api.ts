import { accountApi } from "@/lib/api/account";
import { analyticsApi } from "@/lib/api/analytics";
import { attachmentsApi } from "@/lib/api/attachments";
import { chatsApi } from "@/lib/api/chats";
import { discoverApi } from "@/lib/api/discover";
import { imagesApi } from "@/lib/api/images";
import { integrationsApi } from "@/lib/api/integrations";
import { jobSearchApi } from "@/features/job-search/api";
import { learningApi } from "@/features/learning/api";
import { memoriesApi } from "@/lib/api/memories";
import { speechApi } from "@/lib/api/speech";
import { todosApi } from "@/features/todos/api";

export type * from "@/lib/api/types";
export type { ProductEventName } from "@/lib/api/analytics";
export type * from "@/features/job-search/api";
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
  ...learningApi,
  ...integrationsApi,
  ...attachmentsApi,
  ...imagesApi,
  ...speechApi,
  ...jobSearchApi,
};
