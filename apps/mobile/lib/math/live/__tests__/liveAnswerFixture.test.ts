/**
 * docs/fixtures/live_answer_cases.json holds math keyboard drafts and SymPy's value for each,
 * and the API's test (test_live_answer_fixture.py) holds the chat turn to the same values:
 * the answer the composer shows while typing is the one Send verifies. A null value is a
 * draft that shows no live answer, `"undefined"` one that says undefined, and a list a ± draft's
 * values, in the order the composer shows them.
 */
import fixture from "../../../../../../docs/fixtures/live_answer_cases.json";
import { liveAnswer, liveValuesForTest } from "@/lib/math/live/answer";
import type { LiveResult } from "@/lib/math/live/evaluate";

type Value = string | string[] | null;
type Case = { id: string; draft: string; sympy: string | string[] | null; value: Value; why?: string };
type Shown = number | "undefined";

const CASES = (fixture as unknown as { cases: Case[] }).cases;
const UNDEFINED = "undefined";

/** `"5/6"`, `"-4"`, `"1.41421356237310"` or `"undefined"`. */
function shownOf(value: string): Shown {
  if (value === UNDEFINED) return UNDEFINED;
  const [top, bottom] = value.split("/");
  return bottom === undefined ? Number(top) : Number(top) / Number(bottom);
}

function resultOf(result: LiveResult): Shown {
  if (result.kind === "undefined") return UNDEFINED;
  return result.kind === "approx" ? result.x : Number(result.r.n) / Number(result.r.d);
}

function agrees(got: Shown, want: Shown): boolean {
  if (got === UNDEFINED || want === UNDEFINED) return got === want;
  return Math.abs(got - want) <= 1e-9 * Math.max(1, Math.abs(want));
}

describe("live answer parity with the server", () => {
  it("has answers, undefined values, ± branches and refusals to check", () => {
    expect(CASES.filter((c) => typeof c.value === "string" && c.value !== UNDEFINED).length).toBeGreaterThan(60);
    expect(CASES.filter((c) => c.value === UNDEFINED).length).toBeGreaterThan(5);
    expect(CASES.filter((c) => Array.isArray(c.value)).length).toBeGreaterThan(5);
    expect(CASES.filter((c) => c.value === null).length).toBeGreaterThan(15);
  });

  it.each(CASES.map((c) => [c.id, c] as const))("%s", (_id, c) => {
    const values = liveValuesForTest(c.draft)?.map(resultOf) ?? null;
    if (c.value === null) {
      expect({ draft: c.draft, values }).toEqual({ draft: c.draft, values: null });
      expect(liveAnswer(c.draft, UNDEFINED)).toBeNull();
      return;
    }
    const want = (Array.isArray(c.value) ? c.value : [c.value]).map(shownOf);
    expect(values).not.toBeNull();
    const same = values!.length === want.length && values!.every((got, i) => agrees(got, want[i]!));
    expect({ draft: c.draft, values, same }).toEqual({ draft: c.draft, values, same: true });
  });
});
