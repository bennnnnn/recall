import { accountApi } from "@/lib/api/account";
import { analyticsApi } from "@/lib/api/analytics";
import { pushApi } from "@/lib/api/push";
import { attachmentsApi } from "@/features/attachments/api";
import { chatsApi } from "@/lib/api/chats";
import { discoverApi } from "@/lib/api/discover";
import { imagesApi } from "@/features/images/api";
import { integrationsApi } from "@/features/integrations/api";
import { jobSearchApi } from "@/features/job-search/api";
import { learningApi } from "@/features/learning/api";
import { memoriesApi } from "@/features/memory/api";
import { speechApi } from "@/features/speech/api";
import { todosApi } from "@/features/todos/api";

export type * from "@/lib/api/types";
export type { ProductEventName } from "@/lib/api/analytics";
export type * from "@/features/job-search/api";
export { attachmentRecordExists } from "@/features/attachments/api";
export type { AttachmentListItem } from "@/features/attachments/types";
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
  ...pushApi,
  ...attachmentsApi,
  ...imagesApi,
  ...speechApi,
  ...jobSearchApi,
};
