import MarkdownIt from "markdown-it";
import taskLists from "markdown-it-task-lists";

export const markdownItInstance = MarkdownIt({
  typographer: true,
  linkify: true,
}).use(taskLists, {
  enabled: true,
  label: true,
});
