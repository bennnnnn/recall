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
let mockSession = 0;
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession, requireTokenSession: jest.fn() }));

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
    mockSession++;
    invalidateSuggestedRemindersCache();
  });

  it("does not decrement the count twice for the same suggestion", () => {
    setSuggestedRemindersCache({ ...sample, pending_count: 5 });
    removeSuggestedReminderFromCache("r1");
    removeSuggestedReminderFromCache("r1");
    expect(getCachedSuggestedReminders()?.pending_count).toBe(4);
  });

  it("replays a dismissal over a read already in flight", async () => {
    setSuggestedRemindersCache(sample);
    let resolve!: (data: typeof sample) => void;
    listSuggestedReminders.mockReturnValue(new Promise((yes) => { resolve = yes; }));
    const pending = fetchSuggestedReminders("token", { force: true });
    removeSuggestedReminderFromCache("r1");
    resolve(sample);
    expect(await pending).toEqual({ reminders: [], pending_count: 0 });
    expect(getCachedSuggestedReminders()?.reminders).toEqual([]);
  });

  it("discards a previous account's read before asynchronous sign-out cleanup", async () => {
    let resolve!: (data: typeof sample) => void;
    listSuggestedReminders.mockReturnValueOnce(new Promise((yes) => { resolve = yes; }));
    const pending = fetchSuggestedReminders("token", { force: true });
    mockSession++;
    setSuggestedRemindersCache({ reminders: [], pending_count: 0 });
    resolve(sample);
    expect(await pending).toBeNull();
    expect(getCachedSuggestedReminders()?.reminders).toEqual([]);
  });

  it("does not repopulate suggestions after integration disconnect invalidates a read", async () => {
    let resolve!: (data: typeof sample) => void;
    listSuggestedReminders.mockReturnValueOnce(new Promise((yes) => { resolve = yes; }));
    const pending = fetchSuggestedReminders("token", { force: true });
    invalidateSuggestedRemindersCache();
    resolve(sample);
    expect(await pending).toBeNull();
    expect(getCachedSuggestedReminders()).toBeUndefined();
  });

  it("ignores a previous account's mutation settlement", () => {
    const oldSession = mockSession;
    mockSession++;
    setSuggestedRemindersCache(sample);
    removeSuggestedReminderFromCache("r1", oldSession);
    restoreSuggestedReminderToCache({ ...sample.reminders[0]!, id: "old-account" }, oldSession);
    expect(getCachedSuggestedReminders()).toEqual(sample);
  });

  it("fetches authoritative suggestions after a pending read carrying a failed rollback", async () => {
    setSuggestedRemindersCache(sample);
    let resolve!: (data: typeof sample) => void;
    listSuggestedReminders.mockReturnValueOnce(new Promise((yes) => { resolve = yes; }))
      .mockResolvedValueOnce({ reminders: [], pending_count: 0 });
    const read = fetchSuggestedReminders("token", { force: true });
    removeSuggestedReminderFromCache("r1");
    restoreSuggestedReminderToCache(sample.reminders[0]!);
    const recovery = fetchSuggestedReminders("token", { force: true, afterPending: true });
    resolve({ reminders: [], pending_count: 0 });
    await read;
    expect(await recovery).toEqual({ reminders: [], pending_count: 0 });
    expect(listSuggestedReminders).toHaveBeenCalledTimes(2);
  });

  it("does not start recovery with an old token after changing accounts", async () => {
    let resolve!: (data: typeof sample) => void;
    listSuggestedReminders.mockReturnValueOnce(new Promise((yes) => { resolve = yes; }));
    const read = fetchSuggestedReminders("token", { force: true });
    const recovery = fetchSuggestedReminders("token", { force: true, afterPending: true });
    mockSession++;
    resolve(sample);
    expect(await read).toBeNull();
    expect(await recovery).toBeNull();
    expect(listSuggestedReminders).toHaveBeenCalledTimes(1);
    expect(getCachedSuggestedReminders()).toBeUndefined();
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
