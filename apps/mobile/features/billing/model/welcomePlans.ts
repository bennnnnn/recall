/**
 * When a free account is offered the plans without asking:
 * - once after the first sign-in on this phone, when its first answer is in, so the plans
 *   come after the user has seen what Recall does (the landing asks for it when it is finished);
 * - on the first open of each day, and once more that day after a chat, ``SECOND_OFFER_AFTER_MS``
 *   after the first, so at most twice a day;
 * - when the day's free allowance runs out, once that day.
 * Device preferences like onboarding (`lib/onboarding.ts`), read from their files each time,
 * so no account's data is kept here.
 */
import { prefFilePath, readPrefFile, writePrefFile } from "@/lib/filePrefs";

const WELCOME_FILE = "recall.welcome_plans.txt";
/** "day|shown|lastAt|creditDay": four fields, so a damaged file reads as no offers yet. */
const OFFERS_FILE = "recall.plans_offers.txt";

/** The wait between the day's first offer and its second, which only a chat brings. */
export const SECOND_OFFER_AFTER_MS = 4 * 60 * 60 * 1000;
const OFFERS_A_DAY = 2;

type PlansOffer = "welcome" | "nudge";
/** The app was opened or came back, or a reply just finished. */
export type OfferMoment = "open" | "chatted";

type Offers = { day: string; shown: number; lastAt: number; creditDay: string };

/** The phone's own calendar day: "first open of the day" is the user's day. */
function dayOf(now: number): string {
  const date = new Date(now);
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
}

async function readOffers(): Promise<Offers> {
  const [day = "", shown = "", lastAt = "", creditDay = ""] = (
    (await readPrefFile(prefFilePath(OFFERS_FILE))) ?? ""
  ).split("|");
  const count = (text: string) =>
    Number.isFinite(Number(text)) ? Number(text) : 0;
  return { day, shown: count(shown), lastAt: count(lastAt), creditDay };
}

async function writeOffers(offers: Offers): Promise<void> {
  const { day, shown, lastAt, creditDay } = offers;
  await writePrefFile(
    prefFilePath(OFFERS_FILE),
    [day, shown, lastAt, creditDay].join("|"),
  );
}

/**
 * Each offer reads and writes the file in turn. A reply that uses up the allowance is a
 * "chatted" moment and an out-of-credit one at once; both reading the old file, the later
 * write would drop the other's.
 */
let pending: Promise<unknown> = Promise.resolve();

function inTurn<T>(work: () => Promise<T>): Promise<T> {
  const done = pending.then(work, work);
  pending = done.catch(() => undefined);
  return done;
}

export async function offerPlansAfterSignIn(): Promise<void> {
  await writePrefFile(prefFilePath(WELCOME_FILE), "1");
}

/** The offer due at this moment, if any; one returned is used up. */
export function takePlansOffer(
  moment: OfferMoment,
  now: number = Date.now(),
): Promise<PlansOffer | null> {
  return inTurn(() => nextPlansOffer(moment, now));
}

async function nextPlansOffer(
  moment: OfferMoment,
  now: number,
): Promise<PlansOffer | null> {
  const welcome = prefFilePath(WELCOME_FILE);
  const stored = await readOffers();
  const day = dayOf(now);
  const offers = stored.day === day ? stored : { ...stored, day, shown: 0 };
  if ((await readPrefFile(welcome)) === "1") {
    // Before the first answer, nothing is offered: no plans ahead of any value.
    if (moment !== "chatted") return null;
    await Promise.all([
      writePrefFile(welcome, "0"),
      writeOffers({ ...offers, shown: 1, lastAt: now }),
    ]);
    return "welcome";
  }
  const first = offers.shown === 0;
  const second =
    moment === "chatted" &&
    offers.shown < OFFERS_A_DAY &&
    now - offers.lastAt >= SECOND_OFFER_AFTER_MS;
  if (!first && !second) return null;
  await writeOffers({ ...offers, shown: offers.shown + 1, lastAt: now });
  return "nudge";
}

/** True once a day, when the day's free allowance has just run out. */
export function takeOutOfCreditOffer(
  now: number = Date.now(),
): Promise<boolean> {
  return inTurn(async () => {
    const offers = await readOffers();
    const day = dayOf(now);
    if (offers.creditDay === day) return false;
    await writeOffers({ ...offers, creditDay: day });
    return true;
  });
}
