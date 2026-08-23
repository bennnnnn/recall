import { api, type SuggestedReminder } from "@/lib/api";
import {
  fetchSuggestedReminders,
  getCachedSuggestedReminders,
  invalidateSuggestedRemindersCache,
  isSuggestedRemindersFresh,
  dropSuggestedReminder,
  removeSuggestedReminderFromCache,
  restoreSuggestedReminderToCache,
  setSuggestedRemindersCache,
  undeleteSuggestedReminder,
} from "@/lib/cache/suggestedRemindersCache";

jest.mock("@/lib/api", () => ({
  api: {
    listSuggestedReminders: jest.fn(),
  },
}));

const listSuggestedReminders = api.listSuggestedReminders as jest.Mock;

const sample = {
  reminders: [
    {
      id: "r1",
      title: "Reply to Alex",
      due_at: null,
      notes: null,
      confidence: 0.8,
      source_snippet: "Can we meet?",
      source_sender: "Alex",
      status: "pending",
      created_at: "2026-01-01T00:00:00Z",
      gmail_message_id: "m1",
    },
  ],
  pending_count: 1,
};

describe("suggestedRemindersCache", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    invalidateSuggestedRemindersCache();
  });

  it("returns cached reminders without refetching when fresh", async () => {
    setSuggestedRemindersCache(sample);
    expect(isSuggestedRemindersFresh()).toBe(true);
    expect(getCachedSuggestedReminders()).toEqual(sample);

    const result = await fetchSuggestedReminders("token");
    expect(result).toEqual(sample);
    expect(listSuggestedReminders).not.toHaveBeenCalled();
  });

  it("dedupes concurrent fetches", async () => {
    let resolveFetch!: (value: typeof sample) => void;
    listSuggestedReminders.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );

    const first = fetchSuggestedReminders("token", { force: true });
    const second = fetchSuggestedReminders("token", { force: true });
    resolveFetch(sample);

    const [a, b] = await Promise.all([first, second]);
    expect(a).toEqual(sample);
    expect(b).toEqual(sample);
    expect(listSuggestedReminders).toHaveBeenCalledTimes(1);
  });

  it("drops a reminder from the cache after add/dismiss", () => {
    setSuggestedRemindersCache(sample);
    removeSuggestedReminderFromCache("r1");
    expect(getCachedSuggestedReminders()?.reminders).toEqual([]);
    expect(getCachedSuggestedReminders()?.pending_count).toBe(0);
  });

  it("restores a reminder after a failed add/dismiss", () => {
    setSuggestedRemindersCache(sample);
    const reminder = sample.reminders[0]!;
    removeSuggestedReminderFromCache("r1");
    restoreSuggestedReminderToCache(reminder);
    expect(getCachedSuggestedReminders()?.reminders).toEqual(sample.reminders);
    expect(getCachedSuggestedReminders()?.pending_count).toBe(1);
  });

  it("drops and undeletes cache plus list together", () => {
    setSuggestedRemindersCache(sample);
    const reminder = sample.reminders[0]!;
    let list: SuggestedReminder[] = sample.reminders;
    const setReminders = (updater: (prev: SuggestedReminder[]) => SuggestedReminder[]) => {
      list = updater(list);
    };
    dropSuggestedReminder("r1", setReminders);
    expect(list).toEqual([]);
    expect(getCachedSuggestedReminders()?.reminders).toEqual([]);
    undeleteSuggestedReminder(reminder, setReminders);
    expect(list).toEqual(sample.reminders);
    expect(getCachedSuggestedReminders()?.reminders).toEqual(sample.reminders);
  });
});
