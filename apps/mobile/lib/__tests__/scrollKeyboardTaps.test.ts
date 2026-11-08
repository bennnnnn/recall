import { appFiles, isTest, readSource, relative } from "./support/sourceFiles";

/**
 * Every scroll container says what a tap does while the keyboard is up. React Native's
 * responder walks the React tree, not the native one, so a sheet drawn inside a page's
 * ScrollView still has that ScrollView above it. One left at the default ("never") takes
 * every tap in the capture phase while the keyboard is up and spends it closing the
 * keyboard: Edit profile's Save and Cancel took two taps on iOS (2026-11-07), and a button
 * inside a horizontal maths scroller did the same under the chat's "handled" list.
 */
const SCROLLER = /(?<![\w.])<((?:Animated\.)?(?:ScrollView|FlatList|SectionList)|FlashList)\b/g;

/** The opening tag's text, from `<Name` to the `>` that closes it outside any `{…}`. */
function openingTag(source: string, start: number): string {
  let depth = 0;
  for (let i = start + 1; i < source.length; i += 1) {
    const ch = source[i];
    if (ch === "{") depth += 1;
    else if (ch === "}") depth -= 1;
    else if (ch === ">" && depth === 0 && source[i - 1] !== "=") return source.slice(start, i);
  }
  return source.slice(start);
}

it("gives every scroll container an explicit keyboardShouldPersistTaps", () => {
  const unset = appFiles()
    .filter((file) => file.endsWith(".tsx") && !isTest(file))
    .flatMap((file) => {
      const source = readSource(file);
      return [...source.matchAll(SCROLLER)]
        .filter((m) => !openingTag(source, m.index).includes("keyboardShouldPersistTaps"))
        .map((m) => `${relative(file)}:${source.slice(0, m.index).split("\n").length} ${m[1]}`);
    });
  expect(unset).toEqual([]);
});

it("finds the scroll containers it checks", () => {
  // A pattern that stopped matching would pass the check above with nothing to check.
  const found = appFiles()
    .filter((file) => file.endsWith(".tsx") && !isTest(file))
    .reduce((count, file) => count + [...readSource(file).matchAll(SCROLLER)].length, 0);
  expect(found).toBeGreaterThan(30);
});

it("turns spell-check off wherever autocorrect is off", () => {
  // Names and addresses are no dictionary words. With spell-check on, iOS hung its suggestion
  // bubble ("Bini ↩ | mini | bin") over Edit profile's Save after a deletion, and the tap on
  // Save went to the bubble (2026-11-07).
  const FIELD = /(?<![\w.])<(TextInput|TextField)\b/g;
  const unset = appFiles()
    .filter((file) => file.endsWith(".tsx") && !isTest(file))
    .flatMap((file) => {
      const source = readSource(file);
      return [...source.matchAll(FIELD)]
        .map((m) => ({ m, tag: openingTag(source, m.index) }))
        .filter(({ tag }) => tag.includes("autoCorrect={false}") && !tag.includes("spellCheck"))
        .map(({ m }) => `${relative(file)}:${source.slice(0, m.index).split("\n").length}`);
    });
  expect(unset).toEqual([]);
});
