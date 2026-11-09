/**
 * Structural guard: a domain lives in one folder, not a folder plus siblings.
 *
 * lib/math/ once held nine files while fifteen more sat flat beside it, and
 * lib/chat/ held nine against sixteen. Both started with a single module that
 * was one line cheaper to drop in lib/ than to move into the folder. This
 * test fails on the next one.
 *
 * A domain with no folder yet is caught too: chart, fence, mermaid and share
 * code had grown to 23 flat modules (seven `chart…` files alone) because the
 * check above only looked beside a folder. Three flat modules that share a
 * first word are a domain, and a domain gets a folder.
 *
 * The lib jest project pins `types: ["jest"]` and @types/node is not
 * installed, so the two node shapes this needs are declared here rather than
 * widening the project's types for one test.
 */

declare const __dirname: string;
// eslint-disable-next-line @typescript-eslint/no-require-imports -- @types/node is not installed, so node:fs is required untyped
const { readdirSync, statSync } = require("node:fs") as {
  readdirSync: (path: string) => string[];
  statSync: (path: string) => { isDirectory: () => boolean };
};

const LIB = `${__dirname}/..`;

/** Folders whose domain is also spelled as a different module prefix. */
const PREFIX_ALIASES: Record<string, string[]> = {
  chemistry: ["molecule"],
  images: ["image"],
  speech: ["cloud", "lesson", "liveTalk", "pronunciation", "realtime", "tts", "voice"],
  todos: ["homeReminder", "homeUrgent", "reminder", "todo"],
};

/** Vendored code keeps upstream names; it is not one of our domains. */
const NOT_A_DOMAIN = new Set(["vendor"]);

/** How many flat modules sharing a first word make a domain that needs its folder. */
const FOLDER_AT = 3;

/**
 * First words that name no domain: `appEvents`, `appFonts` and `appVersion` only share it,
 * and a hook's `use` or a test's `is` says what a module is, not what it is about.
 */
const NOT_A_DOMAIN_WORD = new Set(["app", "use", "is"]);

/**
 * Domains still flat from before the rule, each at its size then. None may grow: the
 * next module of one moves the whole domain into a folder (and leaves this list).
 */
const FLAT_DOMAINS: Record<string, number> = {
  accent: 3,
  appearance: 3,
  device: 3,
  link: 3,
};

function domainFolders(): string[] {
  return readdirSync(LIB)
    .filter((name: string) => !name.startsWith("_") && !name.startsWith("."))
    .filter((name: string) => !NOT_A_DOMAIN.has(name))
    .filter((name: string) => statSync(`${LIB}/${name}`).isDirectory())
    .sort();
}

function flatModules(): string[] {
  return readdirSync(LIB)
    .filter((name: string) => /\.tsx?$/.test(name))
    .map((name: string) => name.replace(/\.tsx?$/, ""))
    .sort();
}

/**
 * A flat `mathFoo.ts` beside `math/` shadows the domain folder; `cachedUser`
 * does not shadow `cache/`.
 *
 * An exact match is the barrel idiom, not a split: lib/api.ts re-exports
 * lib/api/* on purpose and CLAUDE.md requires it to stay the single network
 * boundary. Only a camelCase extension of a folder name is a stray module.
 */
function shadows(module: string, prefix: string, exactBarrelAllowed = false): boolean {
  if (module === prefix) return !exactBarrelAllowed;
  if (!module.startsWith(prefix)) return false;
  const next = module[prefix.length];
  return next !== undefined && next === next.toUpperCase() && next !== next.toLowerCase();
}

/** The module's name in `folder` when it shadows that folder: the folder's word dropped. */
function destinationIn(module: string, folder: string): string | null {
  const prefix = [folder, ...(PREFIX_ALIASES[folder] ?? [])].find((candidate, index) =>
    shadows(module, candidate, index === 0),
  );
  if (prefix === undefined) return null;
  const rest = module.slice(prefix.length);
  return rest ? `${rest.slice(0, 1).toLowerCase()}${rest.slice(1)}` : module;
}

/** `chartSpec` → `chart`, `mdFenceScan` → `md`: the word a module's name starts with. */
function firstWord(module: string): string {
  return /^[a-z0-9]+/.exec(module)?.[0] ?? module;
}

/** First word -> the flat modules that start with it, for the words that may be a domain. */
function flatDomains(modules: string[], folders: string[]): Record<string, string[]> {
  const domains: Record<string, string[]> = {};
  for (const module of modules) {
    const word = firstWord(module);
    // `cachedUser` beside `cache/` is no `cached` domain asking for a folder of its own.
    if (NOT_A_DOMAIN_WORD.has(word) || folders.some((folder) => word.startsWith(folder))) continue;
    (domains[word] ??= []).push(module);
  }
  return domains;
}

/** The domains with too many flat modules for no folder: three, or more than recorded. */
function crowdedDomains(modules: string[], folders: string[]): Record<string, string[]> {
  return Object.fromEntries(
    Object.entries(flatDomains(modules, folders)).filter(
      ([word, members]) => members.length >= Math.max(FOLDER_AT, (FLAT_DOMAINS[word] ?? 0) + 1),
    ),
  );
}

describe("lib layout", () => {
  const folders = domainFolders();

  it.each(flatModules())("lib/%s.ts does not shadow a domain folder", (module: string) => {
    for (const folder of folders) {
      const destination = destinationIn(module, folder);
      if (destination) {
        throw new Error(
          `lib/${module}.ts belongs inside lib/${folder}/ as ` +
            `${destination}.ts — a domain with a folder ` +
            `does not also keep modules beside it.`,
        );
      }
    }
  });

  it("finds a stray module by its folder's word", () => {
    expect(destinationIn("chartSpec", "chart")).toBe("spec");
    expect(destinationIn("cachedUser", "cache")).toBeNull();
    // The barrel idiom (lib/api.ts over lib/api/).
    expect(destinationIn("fence", "fence")).toBeNull();
  });

  it(`gives a domain of ${FOLDER_AT} flat modules its folder`, () => {
    // Move the domain's modules into lib/<word>/ (`chartSpec.ts` → `chart/spec.ts`).
    expect(crowdedDomains(flatModules(), folders)).toEqual({});
  });

  it("counts a domain without a folder by the word its modules start with", () => {
    const charts = ["chartSpec", "chartJsSpec", "chartPresentation"];
    expect(crowdedDomains([...charts, "networkProbe", "networkStatus"], [])).toEqual({ chart: charts });
    // A folder's own modules are the check above's; a word that names no domain is no domain.
    expect(crowdedDomains(charts, ["chart"])).toEqual({});
    expect(crowdedDomains(["appEvents", "appFonts", "appVersion"], [])).toEqual({});
    // A domain still flat may not grow.
    const accent = ["accent", "accentPrefs", "accentRuntime", "accentWheel"];
    expect(crowdedDomains(accent.slice(0, 3), [])).toEqual({});
    expect(crowdedDomains(accent, [])).toEqual({ accent });
  });

  it("records each domain still flat at its size", () => {
    const domains = flatDomains(flatModules(), folders);
    const sizes = Object.fromEntries(Object.keys(FLAT_DOMAINS).map((word) => [word, domains[word]?.length ?? 0]));
    // Smaller, or moved into its folder: lower its size here, or drop it.
    expect(sizes).toEqual(FLAT_DOMAINS);
  });
});
