import MarkdownIt from "markdown-it";
import taskLists from "markdown-it-task-lists";

// `tables` is a valid markdown-it option (GFM tables) but is missing from
// @types/markdown-it's Options interface, so cast the config to bypass it.
const mdOptions = {
  typographer: true,
  linkify: true,
  tables: true,
} as unknown as ConstructorParameters<typeof MarkdownIt>[0];

export const markdownItInstance = MarkdownIt(mdOptions).use(taskLists, {
  enabled: true,
  label: true,
});

// Preserve literal variable labels like (c) and math shorthand like +/-.
// Smart quotes remain available independently of symbol substitutions.
markdownItInstance.core.ruler.disable("replacements");
