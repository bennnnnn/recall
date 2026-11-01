/**
 * Structural guard: a catch that drops its error may only grow rarer.
 *
 * These throw the failure away: nothing reaches Sentry or the console, and the screen
 * quietly does something else.
 * - a `catch {}` that does nothing: empty, a comment, a bare `return;` or a stray `;`;
 * - a promise rejection handler (`.catch(h)`, or the second argument of `.then(ok, h)`)
 *   that does nothing: `() => {}`, `() => undefined`, `(_e) => void 0`, a body of bare
 *   `return;`, `noop`, or a function this file declares that does nothing.
 * A handler that returns a value, even `() => null`, states a fallback and is not counted.
 *
 * Today's are counted per file in `emptyCatchBaseline.json`; no file may gain one. Report
 * the error (`captureException`, a warning), or say in code what the fallback is. After
 * removing one, rerun with `UPDATE_EMPTY_CATCHES=1` to lower the count.
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

/** Library no-ops a handler may be named by (`noop`, `_.noop`). */
const NO_OP_NAMES = new Set(["noop"]);

/** `undefined` or `void x`: an expression that is nothing. */
function isNothing(node: ts.Expression): boolean {
  if (ts.isParenthesizedExpression(node)) return isNothing(node.expression);
  return (ts.isIdentifier(node) && node.text === "undefined") || ts.isVoidExpression(node);
}

/** `;` or a bare `return;`: a statement that only ends. */
function onlyEnds(statement: ts.Statement): boolean {
  return ts.isEmptyStatement(statement) || (ts.isReturnStatement(statement) && !statement.expression);
}

/** A function whose body does nothing: empty, bare returns, or an expression that is nothing. */
function doesNothing(node: ts.Node): boolean {
  if (!(ts.isArrowFunction(node) || ts.isFunctionExpression(node) || ts.isFunctionDeclaration(node))) {
    return false;
  }
  const body = node.body;
  if (!body) return false;
  if (!ts.isBlock(body)) return isNothing(body);
  return body.statements.every(
    (statement) =>
      onlyEnds(statement) ||
      (ts.isReturnStatement(statement) && statement.expression !== undefined && isNothing(statement.expression)),
  );
}

/** Names this file gives to functions that do nothing (`const ignore = () => undefined`). */
function localNoOps(source: ts.SourceFile): Set<string> {
  const names = new Set<string>();
  const visit = (node: ts.Node): void => {
    if (ts.isFunctionDeclaration(node) && node.name && doesNothing(node)) names.add(node.name.text);
    if (
      ts.isVariableDeclaration(node) &&
      ts.isIdentifier(node.name) &&
      node.initializer &&
      doesNothing(node.initializer)
    ) {
      names.add(node.name.text);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return names;
}

function isNoOpHandler(node: ts.Expression | undefined, noOps: Set<string>): boolean {
  if (!node) return false;
  if (ts.isIdentifier(node)) return NO_OP_NAMES.has(node.text) || noOps.has(node.text);
  if (ts.isPropertyAccessExpression(node)) return NO_OP_NAMES.has(node.name.text);
  return doesNothing(node);
}

/** The rejection handler of `p.catch(h)` or `p.then(ok, h)`, if `node` is one of those calls. */
function rejectionHandler(node: ts.Node): ts.Expression | undefined {
  if (!ts.isCallExpression(node) || !ts.isPropertyAccessExpression(node.expression)) return undefined;
  const method = node.expression.name.text;
  if (method === "catch") return node.arguments[0];
  if (method === "then") return node.arguments[1];
  return undefined;
}

/** Catch clauses and rejection handlers that do nothing, in `source`. */
function emptyCatches(source: ts.SourceFile): number {
  const noOps = localNoOps(source);
  let count = 0;
  const visit = (node: ts.Node): void => {
    // A catch's `return undefined` is its function's stated fallback, as `return null` is.
    if (ts.isCatchClause(node) && node.block.statements.every(onlyEnds)) count += 1;
    if (isNoOpHandler(rejectionHandler(node), noOps)) count += 1;
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
    const parse = (lines: string[]): ts.SourceFile =>
      ts.createSourceFile("x.ts", lines.join("\n"), ts.ScriptTarget.Latest, true);
    const dropped = [
      "try { a(); } catch {}",
      "try { a(); } catch (error) { /* ignored */ }",
      "load().catch(() => {});",
      "load().catch(async () => {});",
      "load().catch(function () {});",
      "load().catch(() => undefined);",
      "load().catch((_e) => void 0);",
      "load().catch(() => { return; });",
      "load().catch(noop);",
      "load().catch(_.noop);",
      "load().then(show, () => {});",
      "const ignore = () => undefined; load().catch(ignore);",
      // 2026-11-01: a catch that only ends the function dropped its error unseen.
      "function f() { try { a(); } catch { return; } }",
      "function f() { try { a(); } catch (error) { ; } }",
      "load().catch(() => { ; });",
    ];
    const kept = [
      "try { a(); } catch (error) { captureException(error); }",
      "try { a(); } catch { return null; }",
      "function f() { try { a(); } catch { return false; } }",
      "function f(): string | undefined { try { return a(); } catch { return undefined; } }",
      "for (const x of xs) { try { a(x); } catch { continue; } }",
      "load().catch((error) => report(error));",
      "load().catch(report);",
      "load().catch(() => null);",
      "load().then(show);",
      "load().then(() => {});",
    ];
    expect(emptyCatches(parse(dropped))).toBe(dropped.length);
    expect(emptyCatches(parse(kept))).toBe(0);
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
