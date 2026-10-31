/**
 * Structural guard: a catch that drops its error may only grow rarer.
 *
 * An empty `catch {}` (or one holding only a comment) and an empty `.catch(() => {})`
 * throw the failure away: nothing reaches Sentry or the console, and the screen quietly
 * does something else. Today's are counted per file in `emptyCatchBaseline.json`; no file
 * may gain one. Report the error (`captureException`, a warning), or say in code what the
 * fallback is. After removing one, rerun with `UPDATE_EMPTY_CATCHES=1` to lower the count.
 */
import * as ts from "typescript";

import { relative } from "./support/sourceFiles";
import {
  compareWithBaseline,
  parseSource,
  productionFiles,
  recordedBaseline,
} from "./support/ratchet";

declare const __dirname: string;

const BASELINE = `${__dirname}/emptyCatchBaseline.json`;

function isEmptyHandler(node: ts.Expression | undefined): boolean {
  if (!node || !(ts.isArrowFunction(node) || ts.isFunctionExpression(node))) return false;
  return ts.isBlock(node.body) && node.body.statements.length === 0;
}

/** Empty catch clauses and empty `.catch(handler)` calls in `source`. */
function emptyCatches(source: ts.SourceFile): number {
  let count = 0;
  const visit = (node: ts.Node): void => {
    if (ts.isCatchClause(node) && node.block.statements.length === 0) count += 1;
    if (
      ts.isCallExpression(node) &&
      ts.isPropertyAccessExpression(node.expression) &&
      node.expression.name.text === "catch" &&
      isEmptyHandler(node.arguments[0])
    ) {
      count += 1;
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return count;
}

/** File -> empty catches, for every production file with one. */
function emptyCatchCounts(): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const file of productionFiles()) {
    const count = emptyCatches(parseSource(file));
    if (count > 0) counts[relative(file)] = count;
  }
  return counts;
}

describe("empty catches", () => {
  const counts = emptyCatchCounts();
  const { added, grown, lower } = compareWithBaseline(
    counts,
    recordedBaseline(BASELINE, counts, "UPDATE_EMPTY_CATCHES"),
  );

  it("counts only catches that drop the error", () => {
    const source = ts.createSourceFile(
      "x.ts",
      [
        "try { a(); } catch {}",
        "try { a(); } catch (error) { /* ignored */ }",
        "load().catch(() => {});",
        "load().catch(function () {});",
        "try { a(); } catch (error) { captureException(error); }",
        "try { a(); } catch { return null; }",
        "load().catch((error) => report(error));",
        "load().catch(report);",
      ].join("\n"),
      ts.ScriptTarget.Latest,
      true,
    );
    expect(emptyCatches(source)).toBe(4);
  });

  it("lets no file gain one", () => {
    // Report the error or say in code what the fallback is, instead of recording it.
    expect({ added, grown }).toEqual({ added: [], grown: [] });
  });

  it("records the current counts", () => {
    // Fewer now: rerun with UPDATE_EMPTY_CATCHES=1 to lock it in.
    expect(lower).toEqual([]);
  });
});
