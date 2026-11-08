/**
 * The phone's half of docs/fixtures/search_snippets.json: each line the server cuts
 * (apps/api app/tests/modules/search/test_snippet.py checks markdown -> snippet) is shown
 * here as the drawer shows it, so the two cannot drift. A hit used to show its TeX
 * ("…$t$ = time Required $a$…").
 */
import { snippetText } from "@/features/search/model/snippetText";

import fixture from "../../../../../../docs/fixtures/search_snippets.json";

type Case = { name: string; snippet: string; shown: string; code?: boolean };
const cases: Case[] = fixture.cases;

it.each(cases.map((entry) => [entry.name, entry] as const))("%s", (_name, entry) => {
  expect(snippetText(entry.snippet)).toBe(entry.shown);
  // Outside code, nothing of a formula's source is left: no command, no `$…$` pair.
  if (!entry.code) expect(entry.shown).not.toMatch(/\\[A-Za-z]|\$(?=\S)[^$]*\S\$(?!\d)/);
});
