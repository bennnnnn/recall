/**
 * Structural guard: a catch that drops its error may only grow rarer.
 *
 * These throw the failure away: nothing reaches Sentry or the console, and the screen
 * quietly does something else.
 * - a `catch {}` with no statement that does anything: empty, a comment, `;`, `{}`, a name
 *   or `void 0` on its own, `continue`/`break`, or a `return` of nothing (`return;`,
 *   `return undefined`, `return void 0`);
 * - a promise rejection handler (`.catch(h)`, `["catch"](h)`, or the second argument of
 *   `.then(ok, h)`) that does nothing in the same sense: `() => {}`, `() => undefined`,
 *   `(_e) => void 0`, `noop`, or a function that does nothing, declared in the file or
 *   imported from another (through barrels too).
 * Doing something is a call, an assignment, a throw, or a `return` of a value: a handler
 * that returns a value, even `() => null`, states a fallback and is not counted.
 *
 * Today's are counted per file in `emptyCatchBaseline.json`; no file may gain one. Report
 * the error (`captureException`, a warning), or say in code what the fallback is. After
 * removing one, rerun with `UPDATE_EMPTY_CATCHES=1` to lower the count.
 */
import * as ts from "typescript";

import { ROOT, relative } from "./support/sourceFiles";
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

const ASSIGNMENTS = new Set([
  ts.SyntaxKind.EqualsToken, ts.SyntaxKind.PlusEqualsToken, ts.SyntaxKind.MinusEqualsToken,
  ts.SyntaxKind.AsteriskEqualsToken, ts.SyntaxKind.AsteriskAsteriskEqualsToken, ts.SyntaxKind.SlashEqualsToken,
  ts.SyntaxKind.PercentEqualsToken, ts.SyntaxKind.LessThanLessThanEqualsToken,
  ts.SyntaxKind.GreaterThanGreaterThanEqualsToken, ts.SyntaxKind.GreaterThanGreaterThanGreaterThanEqualsToken,
  ts.SyntaxKind.AmpersandEqualsToken, ts.SyntaxKind.BarEqualsToken, ts.SyntaxKind.CaretEqualsToken,
  ts.SyntaxKind.BarBarEqualsToken, ts.SyntaxKind.AmpersandAmpersandEqualsToken,
  ts.SyntaxKind.QuestionQuestionEqualsToken,
]);

/** A call, `new`, assignment, `++`/`--`, `await`, `yield` or `delete` in `node`, outside nested functions. */
function hasEffect(node: ts.Node): boolean {
  if (ts.isFunctionLike(node)) return false;
  if (
    ts.isCallExpression(node) || ts.isNewExpression(node) || ts.isTaggedTemplateExpression(node) ||
    ts.isAwaitExpression(node) || ts.isYieldExpression(node) || ts.isDeleteExpression(node) ||
    (ts.isBinaryExpression(node) && ASSIGNMENTS.has(node.operatorToken.kind)) ||
    ((ts.isPrefixUnaryExpression(node) || ts.isPostfixUnaryExpression(node)) &&
      (node.operator === ts.SyntaxKind.PlusPlusToken || node.operator === ts.SyntaxKind.MinusMinusToken))
  ) {
    return true;
  }
  return ts.forEachChild(node, hasEffect) === true;
}

/** `undefined` or `void x` with no effect: an expression that is nothing. */
function isNothing(node: ts.Expression): boolean {
  if (ts.isParenthesizedExpression(node)) return isNothing(node.expression);
  return (ts.isIdentifier(node) && node.text === "undefined") || (ts.isVoidExpression(node) && !hasEffect(node));
}

/** A statement that does nothing: no call, assignment or throw, and no `return` of a value. */
function isInert(statement: ts.Statement): boolean {
  if (ts.isEmptyStatement(statement) || ts.isContinueStatement(statement) || ts.isBreakStatement(statement)) {
    return true;
  }
  if (ts.isBlock(statement)) return statement.statements.every(isInert);
  if (ts.isExpressionStatement(statement)) return !hasEffect(statement.expression);
  if (ts.isReturnStatement(statement)) return !statement.expression || isNothing(statement.expression);
  if (ts.isIfStatement(statement)) {
    return !hasEffect(statement.expression) && isInert(statement.thenStatement) &&
      (!statement.elseStatement || isInert(statement.elseStatement));
  }
  return false;
}

/** A function whose body does nothing, or whose expression body is nothing. */
function doesNothing(node: ts.Node): boolean {
  if (!(ts.isArrowFunction(node) || ts.isFunctionExpression(node) || ts.isFunctionDeclaration(node))) {
    return false;
  }
  const body = node.body;
  if (!body) return false;
  return ts.isBlock(body) ? body.statements.every(isInert) : isNothing(body);
}

const hasModifier = (node: ts.Node, kind: ts.SyntaxKind): boolean =>
  ts.canHaveModifiers(node) && Boolean(ts.getModifiers(node)?.some((modifier) => modifier.kind === kind));

/** Names this file gives to functions that do nothing (`const ignore = () => undefined`), and which it exports. */
function localNoOps(source: ts.SourceFile): { names: Set<string>; exported: Set<string> } {
  const names = new Set<string>();
  const exported = new Set<string>();
  const visit = (node: ts.Node): void => {
    if (ts.isFunctionDeclaration(node) && doesNothing(node)) {
      if (node.name) names.add(node.name.text);
      if (hasModifier(node, ts.SyntaxKind.ExportKeyword)) {
        exported.add(hasModifier(node, ts.SyntaxKind.DefaultKeyword) || !node.name ? "default" : node.name.text);
      }
    }
    if (ts.isVariableStatement(node)) {
      for (const declaration of node.declarationList.declarations) {
        if (!ts.isIdentifier(declaration.name) || !declaration.initializer || !doesNothing(declaration.initializer)) {
          continue;
        }
        names.add(declaration.name.text);
        if (hasModifier(node, ts.SyntaxKind.ExportKeyword)) exported.add(declaration.name.text);
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return { names, exported };
}

/** Finds the file a module specifier names (`@/lib/x`, `./x`), or undefined outside the app. */
type Resolve = (specifier: string, from: string) => ts.SourceFile | undefined;

const moduleText = (node: ts.Expression | undefined): string | undefined =>
  node && ts.isStringLiteral(node) ? node.text : undefined;

/** The names `source` exports for functions that do nothing, through its own re-exports too. */
function exportedNoOps(source: ts.SourceFile, resolve: Resolve, seen = new Set<string>()): Set<string> {
  if (seen.has(source.fileName)) return new Set();
  seen.add(source.fileName);
  const { names, exported } = localNoOps(source);
  for (const node of source.statements) {
    if (!ts.isExportDeclaration(node)) continue;
    const from = moduleText(node.moduleSpecifier);
    const target = from ? resolve(from, source.fileName) : undefined;
    if (from && !target) continue;
    const theirs = target ? exportedNoOps(target, resolve, seen) : names;
    if (!node.exportClause) {
      for (const name of theirs) if (name !== "default") exported.add(name);
    } else if (ts.isNamedExports(node.exportClause)) {
      for (const element of node.exportClause.elements) {
        if (theirs.has((element.propertyName ?? element.name).text)) exported.add(element.name.text);
      }
    }
  }
  return exported;
}

/** Local names `source` imports for functions that do nothing (`import { ignore as skip }`). */
function importedNoOps(source: ts.SourceFile, resolve: Resolve): Set<string> {
  const names = new Set<string>();
  for (const node of source.statements) {
    if (!ts.isImportDeclaration(node) || !node.importClause) continue;
    const from = moduleText(node.moduleSpecifier);
    const target = from ? resolve(from, source.fileName) : undefined;
    if (!target) continue;
    const theirs = exportedNoOps(target, resolve);
    const { name, namedBindings } = node.importClause;
    if (name && theirs.has("default")) names.add(name.text);
    if (namedBindings && ts.isNamedImports(namedBindings)) {
      for (const element of namedBindings.elements) {
        if (theirs.has((element.propertyName ?? element.name).text)) names.add(element.name.text);
      }
    }
  }
  return names;
}

function isNoOpHandler(node: ts.Expression | undefined, noOps: Set<string>): boolean {
  if (!node) return false;
  if (ts.isIdentifier(node)) return NO_OP_NAMES.has(node.text) || noOps.has(node.text);
  if (ts.isPropertyAccessExpression(node)) return NO_OP_NAMES.has(node.name.text);
  return doesNothing(node);
}

/** The rejection handler of `p.catch(h)`, `p["catch"](h)` or `p.then(ok, h)`, if `node` is one of those calls. */
function rejectionHandler(node: ts.Node): ts.Expression | undefined {
  if (!ts.isCallExpression(node)) return undefined;
  const callee = node.expression;
  const method = ts.isPropertyAccessExpression(callee)
    ? callee.name.text
    : ts.isElementAccessExpression(callee) && ts.isStringLiteralLike(callee.argumentExpression)
      ? callee.argumentExpression.text
      : undefined;
  if (method === "catch") return node.arguments[0];
  if (method === "then") return node.arguments[1];
  return undefined;
}

/** Catch clauses and rejection handlers that do nothing, in `source`. */
function emptyCatches(source: ts.SourceFile, resolve: Resolve = () => undefined): number {
  const noOps = new Set([...localNoOps(source).names, ...importedNoOps(source, resolve)]);
  let count = 0;
  const visit = (node: ts.Node): void => {
    if (ts.isCatchClause(node) && node.block.statements.every(isInert)) count += 1;
    if (isNoOpHandler(rejectionHandler(node), noOps)) count += 1;
    ts.forEachChild(node, visit);
  };
  visit(source);
  return count;
}

/** The app's own modules, by `@/` path or relative path, parsed once each. */
function appResolver(): Resolve {
  const parsed = new Map<string, ts.SourceFile>();
  return (specifier, from) => {
    const base = specifier.startsWith("@/")
      ? `${ROOT}/${specifier.slice(2)}`
      : specifier.startsWith(".")
        ? ts.sys.resolvePath(`${from.slice(0, from.lastIndexOf("/"))}/${specifier}`)
        : undefined;
    if (!base) return undefined;
    const file = [base, `${base}.ts`, `${base}.tsx`, `${base}/index.ts`, `${base}/index.tsx`]
      .find((candidate) => /\.tsx?$/.test(candidate) && ts.sys.fileExists(candidate));
    if (!file) return undefined;
    const source = parsed.get(file) ?? parseSource(file);
    parsed.set(file, source);
    return source;
  };
}

/** File -> empty catches, for every production file with one. */
function emptyCatchCounts(): Record<string, number> {
  const resolve = appResolver();
  const counts: Record<string, number> = {};
  for (const file of productionFiles()) {
    const count = emptyCatches(parseSource(file), resolve);
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
  const parse = (lines: string[], name = "x.ts"): ts.SourceFile =>
    ts.createSourceFile(name, lines.join("\n"), ts.ScriptTarget.Latest, true);

  it("counts only catches that drop the error", () => {
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
      // 2026-11-01: catches that did nothing in other words dropped their errors unseen.
      "function f() { try { a(); } catch { return; } }",
      "function f() { try { a(); } catch (error) { ; } }",
      "load().catch(() => { ; });",
      "try { a(); } catch { void 0; }",
      "try { a(); } catch { {} }",
      "function f() { try { a(); } catch { return void 0; } }",
      "function f(): string | undefined { try { return a(); } catch { return undefined; } }",
      "try { a(); } catch (e) { e; }",
      "for (const x of xs) { try { a(x); } catch { continue; } }",
      "for (const x of xs) { try { a(x); } catch { if (x) break; } }",
      "load().catch(() => { {} });",
      'load()["catch"](() => {});',
      "load().catch(function quiet() { return undefined; });",
    ];
    const kept = [
      "try { a(); } catch (error) { captureException(error); }",
      "try { a(); } catch { return null; }",
      "function f() { try { a(); } catch { return false; } }",
      "try { a(); } catch (e) { last = e; }",
      "try { a(); } catch { failures += 1; }",
      "try { a(); } catch { void report(); }",
      "try { a(); } catch (e) { throw e; }",
      "load().catch((error) => report(error));",
      'load()["catch"]((error) => report(error));',
      "load().catch(report);",
      "load().catch(() => null);",
      "load().catch((e) => e);",
      "load().then(show);",
      "load().then(() => {});",
    ];
    for (const line of dropped) expect([line, emptyCatches(parse([line]))]).toEqual([line, 1]);
    for (const line of kept) expect([line, emptyCatches(parse([line]))]).toEqual([line, 0]);
  });

  it("reads a do-nothing handler imported from another file, through a barrel", () => {
    const files = new Map([
      ["./quiet", parse(["export const ignore = () => {};", "export function report(e: unknown) { log(e); }"], "/app/lib/quiet.ts")],
      ["@/lib", parse(['export { ignore as skip, report } from "./quiet";'], "/app/lib/index.ts")],
    ]);
    const resolve: Resolve = (specifier) => files.get(specifier);
    const user = parse([
      'import { skip as hush, report } from "@/lib";',
      "load().catch(hush);",
      "load().catch(report);",
    ], "/app/features/x.ts");
    expect(emptyCatches(user, resolve)).toBe(1);
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
