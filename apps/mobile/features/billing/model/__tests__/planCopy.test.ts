import { planBenefits, PRO_ADDS, yearlySaving } from "@/features/billing/model/planCopy";

declare const __dirname: string;
const { readFileSync } = jest.requireActual<{
  readFileSync(path: string, encoding: "utf8"): string;
}>("node:fs");
const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");

/** `400 * 1024**2` as a number: the products and powers plans.py writes its sizes with. */
function product(text: string): number {
  return text
    .split(/\s+\*\s+/)
    .reduce((total, factor) => total * factor.split("**").map(Number).reduceRight((exponent, base) => base ** exponent), 1);
}

/** The settings of the allowances Free counts as part of its messages (`follow_messages`,
 * named by allowance there; entitlements.py's `_ALLOWANCE_SETTING` names their settings). */
function freeFollowsMessages(): Set<string> {
  const api = join(__dirname, "../../../../../api/app");
  const plans = readFileSync(join(api, "core/settings/plans.py"), "utf8");
  const listed = /^\s{4}follow_messages: list\[str\] = \[([^\]]*)\]/m.exec(plans)?.[1] ?? "";
  const allowances = [...listed.matchAll(/"(\w+)"/g)].map((m) => m[1]!);
  const entitlements = readFileSync(join(api, "modules/billing/entitlements.py"), "utf8");
  const setting = new Map([...entitlements.matchAll(/^\s{4}"(\w+)": "(\w+)",$/gm)].map((m) => [m[1]!, m[2]!]));
  if (allowances.length === 0 || allowances.some((name) => !setting.has(name))) {
    throw new Error("follow_messages or _ALLOWANCE_SETTING could not be read");
  }
  return new Set(allowances.map((name) => setting.get(name)!));
}

/** Each allowance in the server's plan settings: Free's value and Pro's (null = no cap). */
function serverPlans(): Map<string, { free: number | null; pro: number | null }> {
  const source = readFileSync(join(__dirname, "../../../../../api/app/core/settings/plans.py"), "utf8");
  const values = new Map<string, number | null>();
  for (const [, name, raw] of source.matchAll(/^\s{4}(\w+): [^=\n]+= (.+)$/gm)) {
    const text = raw!.trim();
    if (text === "None") values.set(name!, null);
    else if (/^[\d_*\s]+$/.test(text)) values.set(name!, product(text.replaceAll("_", "")));
  }
  const plans = new Map<string, { free: number | null; pro: number | null }>();
  for (const [name, free] of values) {
    if (values.has(`${name}_pro`)) plans.set(name, { free, pro: values.get(`${name}_pro`)! });
  }
  return plans;
}

describe("the plans page's benefits", () => {
  it("lists only what Pro has more of than Free, each from the server's plan settings", () => {
    const plans = serverPlans();
    // Free's searches, lookups and uploads follow its messages: its own cap for one is unused,
    // and what it gets is up to its day's messages (plans.py `follow_messages`).
    const followed = freeFollowsMessages();
    const freeCap = (name: string) => (followed.has(name) ? plans.get("daily_message_limit")!.free : plans.get(name)!.free);
    for (const [line, settings] of Object.entries(PRO_ADDS)) {
      const more = settings.some((name) => {
        const plan = plans.get(name);
        if (!plan) throw new Error(`${line}: ${name} is not a plan setting`);
        const free = freeCap(name);
        return plan.pro === null ? free !== null : free !== null && plan.pro > free;
      });
      expect(`${line}: ${more}`).toBe(`${line}: true`);
    }
  });

  it("names unlimited chat with its fair use, as Pro still has a daily token guard", () => {
    const plans = serverPlans();
    expect(plans.get("daily_message_limit")?.pro).toBeNull();
    expect(plans.get("daily_token_limit")?.pro).toEqual(expect.any(Number));
    const en = jest.requireActual<Record<string, string>>("@/lib/i18n/en.json");
    expect(en["upgrade.benefit_chat"]).toMatch(/fair use/);
    // What Free has too is no Pro benefit.
    const lines = planBenefits((key: string) => key);
    for (const free of ["upgrade.benefit_maths", "upgrade.benefit_scanner", "upgrade.benefit_pdf", "settings.web_search"]) {
      expect(lines).not.toContain(free);
    }
  });
});

describe("yearlySaving", () => {
  it.each([
    // An exact 20%: 1 − 0.8 is 0.19999… in floating point, and still says 20.
    [10, 96, 20],
    [5, 48, 20],
    // 59.99 against 95.88: 37.4%, rounded down, never up.
    [7.99, 59.99, 37],
  ])("monthly %s, yearly %s saves %s%%", (monthly, yearly, percent) => {
    expect(yearlySaving({ monthly: { price: monthly }, yearly: { price: yearly } })).toBe(percent);
  });

  it("says no saving when the year costs as much as twelve months, or a price is missing", () => {
    expect(yearlySaving({ monthly: { price: 5 }, yearly: { price: 60 } })).toBeNull();
    expect(yearlySaving({ monthly: { price: 5 } })).toBeNull();
  });
});
