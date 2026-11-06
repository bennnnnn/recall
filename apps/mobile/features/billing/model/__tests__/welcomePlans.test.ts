import {
  SECOND_OFFER_AFTER_MS,
  offerPlansAfterSignIn,
  takeOutOfCreditOffer,
  takePlansOffer,
} from "@/features/billing/model/welcomePlans";

const mockFiles = new Map<string, string>();
jest.mock("@/lib/filePrefs", () => ({
  prefFilePath: (name: string) => name,
  readPrefFile: async (path: string) => mockFiles.get(path) ?? null,
  writePrefFile: async (path: string, value: string) => {
    mockFiles.set(path, value);
  },
}));

/** 8 in the morning, the phone's time, on a day; ``hours`` later on it. */
const morning = new Date(2026, 10, 6, 8).getTime();
const at = (hours: number) => morning + hours * 60 * 60 * 1000;

beforeEach(() => mockFiles.clear());

it("offers the plans after the first answer, never before it, as the day's first", async () => {
  await offerPlansAfterSignIn();
  expect(await takePlansOffer("open", at(0))).toBeNull();
  expect(await takePlansOffer("chatted", at(0))).toBe("welcome");
  expect(await takePlansOffer("open", at(1))).toBeNull();
});

it("offers on the day's first open, and once more after a chat later that day", async () => {
  expect(await takePlansOffer("open", at(0))).toBe("nudge");
  expect(await takePlansOffer("open", at(5))).toBeNull();
  expect(await takePlansOffer("chatted", at(1))).toBeNull();
  expect(await takePlansOffer("chatted", at(0) + SECOND_OFFER_AFTER_MS)).toBe("nudge");
  // Twice a day at most.
  expect(await takePlansOffer("chatted", at(12))).toBeNull();
  expect(await takePlansOffer("open", at(13))).toBeNull();
});

it("starts again the next day", async () => {
  await takePlansOffer("open", at(0));
  expect(await takePlansOffer("open", at(24))).toBe("nudge");
});

it("offers when the free allowance runs out, once that day", async () => {
  expect(await takeOutOfCreditOffer(at(3))).toBe(true);
  expect(await takeOutOfCreditOffer(at(4))).toBe(false);
  expect(await takeOutOfCreditOffer(at(25))).toBe(true);
});
