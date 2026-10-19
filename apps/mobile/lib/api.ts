import { accountApi } from "@/features/account/api";
import { attachmentsApi } from "@/features/attachments/api";
import { chatsApi } from "@/features/chat/api";
import { homeApi } from "@/features/home/api";
import { imagesApi } from "@/features/images/api";
import { memoriesApi } from "@/features/memory/api";
import { searchApi } from "@/features/search/api";
import { speechApi } from "@/features/speech/api";
import { todosApi } from "@/features/todos/api";
import { analyticsApi } from "@/lib/api/analytics";
import { discoverApi } from "@/lib/api/discover";
import { pushApi } from "@/lib/api/push";
import { scanApi } from "@/lib/api/scan";

export type * from "@/lib/api/types";
export type { ProductEventName } from "@/lib/api/analytics";
export type { ScanReading } from "@/lib/api/scan";
export { attachmentRecordExists } from "@/features/attachments/api";
export type { AttachmentListItem } from "@/features/attachments/types";
export {
  agreeToAiDataSharing,
  loginWithApple,
  loginWithDev,
  loginWithGoogle,
} from "@/features/auth/api";
export { transcribeSpeech } from "@/features/speech/api";
export { chatWebSocketUrl } from "@/lib/api/connectivity";
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
  ...homeApi,
  ...searchApi,
  ...discoverApi,
  ...todosApi,
  ...pushApi,
  ...attachmentsApi,
  ...imagesApi,
  ...speechApi,
  ...scanApi,
};
