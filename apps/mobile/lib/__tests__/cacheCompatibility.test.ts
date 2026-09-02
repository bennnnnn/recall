jest.mock("@/lib/api", () => ({ api: {} }));

import * as canonicalChats from "@/lib/cache/chatListCache";
import * as canonicalIntegrations from "@/lib/cache/integrationStatusCache";
import * as canonicalMemories from "@/lib/cache/memoryListCache";
import * as canonicalReminders from "@/lib/cache/suggestedRemindersCache";
import * as legacyChats from "@/lib/chatListCache";
import * as legacyIntegrations from "@/lib/integrationStatusCache";
import * as legacyMemories from "@/lib/memoryListCache";
import * as legacyReminders from "@/lib/suggestedRemindersCache";

describe("stateful cache compatibility seams", () => {
  it.each([
    ["chat list", legacyChats.setChatListCache, canonicalChats.setChatListCache],
    [
      "integration status",
      legacyIntegrations.setIntegrationStatusCache,
      canonicalIntegrations.setIntegrationStatusCache,
    ],
    ["memory list", legacyMemories.setMemoriesCache, canonicalMemories.setMemoriesCache],
    [
      "suggested reminders",
      legacyReminders.setSuggestedRemindersCache,
      canonicalReminders.setSuggestedRemindersCache,
    ],
  ])("%s legacy export resolves to the canonical singleton module", (_name, legacy, canonical) => {
    expect(legacy).toBe(canonical);
  });
});
