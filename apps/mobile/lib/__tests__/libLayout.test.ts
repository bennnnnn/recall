/**
 * Structural guard: a domain lives in one folder, not a folder plus siblings.
 *
 * lib/math/ once held nine files while fifteen more sat flat beside it, and
 * lib/chat/ held nine against sixteen. Both started with a single module that
 * was one line cheaper to drop in lib/ than to move into the folder. This
 * test fails on the next one.
 *
 * The lib jest project pins `types: ["jest"]` and @types/node is not
 * installed, so the two node shapes this needs are declared here rather than
 * widening the project's types for one test.
 */

declare const __dirname: string;
// eslint-disable-next-line @typescript-eslint/no-require-imports
const { readdirSync, statSync } = require("node:fs") as {
  readdirSync: (path: string) => string[];
  statSync: (path: string) => { isDirectory: () => boolean };
};

const LIB = `${__dirname}/..`;

/** Folders whose domain is also spelled as a different module prefix. */
const PREFIX_ALIASES: Record<string, string[]> = {
  chemistry: ["molecule"],
  images: ["image"],
  projects: ["exportProject", "language", "parseLearning", "parseVocab", "project"],
  todos: ["homeReminder", "homeUrgent", "reminder", "todo"],
};

/** Vendored code keeps upstream names; it is not one of our domains. */
const NOT_A_DOMAIN = new Set(["vendor"]);

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
function shadows(module: string, prefix: string): boolean {
  if (module === prefix) return false;
  if (!module.startsWith(prefix)) return false;
  const next = module[prefix.length];
  return next !== undefined && next === next.toUpperCase() && next !== next.toLowerCase();
}

describe("lib layout", () => {
  const folders = domainFolders();

  it.each(flatModules())("lib/%s.ts does not shadow a domain folder", (module: string) => {
    for (const folder of folders) {
      for (const prefix of [folder, ...(PREFIX_ALIASES[folder] ?? [])]) {
        if (shadows(module, prefix)) {
          throw new Error(
            `lib/${module}.ts belongs inside lib/${folder}/ as ` +
              `${module.slice(prefix.length, prefix.length + 1).toLowerCase()}` +
              `${module.slice(prefix.length + 1)}.ts — a domain with a folder ` +
              `does not also keep modules beside it.`,
          );
        }
      }
    }
  });
});
