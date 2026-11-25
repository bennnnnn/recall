/**
 * The phone's copies of the API's paste rules, held to the API's own sources so the two
 * cannot drift apart (as attachmentLimits.test.ts does for uploads).
 */
import { PASTE_MAX_CHARS, PASTED_TEXT_FILE_NAME } from "@/features/attachments/model/pastedText";
import { MESSAGE_MAX_CHARS } from "@/features/chat/model/messageLimit";

declare const __dirname: string;
const { readFileSync } = jest.requireActual<{
  readFileSync(path: string, encoding: "utf8"): string;
}>("node:fs");
const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");

const API = join(__dirname, "../../../../../api/app");
const read = (path: string) => readFileSync(join(API, path), "utf8");
const number = (source: string, name: string) =>
  Number(source.match(new RegExp(`^${name} = ([\\d_]+)$`, "m"))?.[1]?.replace(/_/g, "") ?? NaN);

it("names the file as the API reads a paste", () => {
  const source = read("modules/attachments/pasted_text.py");
  expect(source).toContain(`PASTED_TEXT_FILENAME = "${PASTED_TEXT_FILE_NAME}"`);
  expect(source).toContain('PASTED_TEXT_CONTENT_TYPE = "text/plain"');
});

it("holds a paste to what the API keeps searchable, the API's own limit", () => {
  expect(read("modules/attachments/pasted_text.py")).toContain("PASTED_TEXT_MAX_CHARS = MAX_INDEX_EXTRACT_CHARS");
  expect(number(read("modules/attachments/text_extract.py"), "MAX_INDEX_EXTRACT_CHARS")).toBe(PASTE_MAX_CHARS);
});

it("holds a draft to the API's message length", () => {
  const source = read("models/schemas/chats.py");
  expect(number(source, "MESSAGE_MAX_CHARS")).toBe(MESSAGE_MAX_CHARS);
  expect(source).toContain("max_length=MESSAGE_MAX_CHARS");
});
