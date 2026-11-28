/**
 * A card a newer Recall draws. A reply is saved once and read by every build, so a card
 * fence added after this build (the server's or the model's, live or in history) reaches
 * it with a tag it does not know: it showed its raw JSON as a code card. Such a fence
 * says "Update Recall to see this" instead (`NewerCardNote`).
 *
 * The phone decides, not the server: the server could leave a new card out of a reply
 * for an old build's `X-App-Version`, but the saved reply then lacks it on every other
 * device, and a reply saved before still reaches the old build from history.
 *
 * Every card fence is a lowercase name (`calculator`, `chem_scene`) around a JSON object,
 * so that is the shape read here, and only when the tag is no language this build knows
 * and no word a model tags its own data with (`response`, `config`). A new card fence
 * keeps that shape (lib/fence/registry.ts).
 */
import { isKnownCodeLang } from "@/lib/codeHighlight";
import { parseJsonRecord } from "@/lib/fence/json";
import { fenceSpecForLang, isPlainTextFenceLang } from "@/lib/fence/registry";

const CARD_TAG = /^[a-z][a-z0-9_]{2,31}$/;

/** Tags a model writes around data of its own: a JSON body under one is the user's data. */
const DATA_WORDS =
  /json|yaml|toml|xml|csv|config|conf|settings|schema|data|payload|response|request|body|api|http|output|input|example|sample|object|dict|map|record|manifest|package|query|event|log|state|props/;

/** A tag that may name a card fence this build does not know (the body is still to check). */
function isNewerCardTag(lang: string): boolean {
  const tag = lang.trim().toLowerCase();
  return (
    CARD_TAG.test(tag) &&
    fenceSpecForLang(tag) === null &&
    !isPlainTextFenceLang(tag) &&
    !isKnownCodeLang(tag) &&
    !DATA_WORDS.test(tag)
  );
}

/** A finished fence a newer build draws as a card. */
export function isNewerCardFence(lang: string, content: string): boolean {
  if (!isNewerCardTag(lang)) return false;
  const record = parseJsonRecord(content.trim());
  return record !== null && Object.keys(record).length > 0;
}

/** The open tail of one while the reply streams: its JSON has only begun. */
export function opensNewerCardFence(lang: string, body: string): boolean {
  return isNewerCardTag(lang) && body.trimStart().startsWith("{");
}
