// Read-only TypeScript metrics for apps/mobile production code (tests, vendor excluded).
// Usage: node ts_metrics.js <mobileRoot> <outDir>
const fs = require("fs");
const path = require("path");
const root = process.argv[2];
const outDir = process.argv[3];
const ts = require(path.join(root, "node_modules/typescript"));

const DIRS = ["app", "components", "contexts", "features", "hooks", "lib", "ui"];
const files = [];
function walk(dir) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    const st = fs.statSync(p);
    if (st.isDirectory()) {
      if (name === "__tests__" || name === "node_modules" || name === "__mocks__" || name === "vendor") continue;
      walk(p);
    } else if (/\.(ts|tsx)$/.test(name) && !/\.(test|spec)\.(ts|tsx)$/.test(name) && !name.endsWith(".d.ts")) {
      files.push(p);
    }
  }
}
for (const d of DIRS) {
  const p = path.join(root, d);
  if (fs.existsSync(p)) walk(p);
}

const funcs = [];
const counts = { any: 0, as: 0, asConst: 0, asUnknownAs: 0, nonNull: 0, tsIgnore: 0, tsExpectError: 0, eslintDisable: 0, catches: 0, catchEmpty: 0, catchSilent: 0 };
const perFile = { any: {}, as: {}, nonNull: {}, asUnknownAs: [] };
const catchRows = [];
const eslintRows = [];
const anyRows = [];

function lineOf(sf, pos) {
  return sf.getLineAndCharacterOfPosition(pos).line + 1;
}

function nameOf(node, sf) {
  if (node.name && node.name.getText) return node.name.getText(sf);
  const parent = node.parent;
  if (parent && ts.isVariableDeclaration(parent) && parent.name) return parent.name.getText(sf);
  if (parent && ts.isPropertyAssignment(parent)) return parent.name.getText(sf);
  if (parent && ts.isCallExpression(parent)) {
    const callee = parent.expression.getText(sf);
    // useCallback(() => ..., []) inside a variable
    const gp = parent.parent;
    if (gp && ts.isVariableDeclaration(gp)) return `${gp.name.getText(sf)}(${callee})`;
    return `<arg of ${callee.slice(0, 30)}>`;
  }
  return "<anon>";
}

const CONTROL = new Set([
  ts.SyntaxKind.IfStatement,
  ts.SyntaxKind.ForStatement,
  ts.SyntaxKind.ForInStatement,
  ts.SyntaxKind.ForOfStatement,
  ts.SyntaxKind.WhileStatement,
  ts.SyntaxKind.DoStatement,
  ts.SyntaxKind.SwitchStatement,
  ts.SyntaxKind.TryStatement,
]);

function isFunc(node) {
  return (
    ts.isFunctionDeclaration(node) ||
    ts.isFunctionExpression(node) ||
    ts.isArrowFunction(node) ||
    ts.isMethodDeclaration(node) ||
    ts.isGetAccessorDeclaration(node) ||
    ts.isSetAccessorDeclaration(node) ||
    ts.isConstructorDeclaration(node)
  );
}

function depthOf(node) {
  let best = 0;
  function visit(n, depth) {
    if (n !== node && isFunc(n)) return;
    let d = depth;
    if (CONTROL.has(n.kind)) {
      // else-if chains stay at the same level
      const isElseIf = ts.isIfStatement(n) && n.parent && ts.isIfStatement(n.parent) && n.parent.elseStatement === n;
      if (!isElseIf) d = depth + 1;
      best = Math.max(best, d);
    }
    ts.forEachChild(n, (c) => visit(c, d));
  }
  ts.forEachChild(node, (c) => visit(c, 0));
  return best;
}

for (const file of files) {
  const src = fs.readFileSync(file, "utf8");
  const kind = file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const sf = ts.createSourceFile(file, src, ts.ScriptTarget.Latest, true, kind);
  const rel = path.relative(path.dirname(path.dirname(root)), file);
  const lines = src.split("\n");
  lines.forEach((l, i) => {
    if (/@ts-ignore/.test(l)) counts.tsIgnore++;
    if (/@ts-expect-error/.test(l)) counts.tsExpectError++;
    if (/eslint-disable/.test(l)) {
      counts.eslintDisable++;
      eslintRows.push(`${rel}:${i + 1}\t${l.trim().slice(0, 160)}`);
    }
  });
  function visit(node) {
    if (isFunc(node)) {
      const start = lineOf(sf, node.getStart(sf));
      const end = lineOf(sf, node.getEnd());
      funcs.push([nameOf(node, sf), rel, start, end - start + 1, depthOf(node)]);
    }
    if (node.kind === ts.SyntaxKind.AnyKeyword) {
      counts.any++;
      perFile.any[rel] = (perFile.any[rel] || 0) + 1;
      anyRows.push(`${rel}:${lineOf(sf, node.getStart(sf))}\t${lines[lineOf(sf, node.getStart(sf)) - 1].trim().slice(0, 140)}`);
    }
    if (ts.isAsExpression(node)) {
      const t = node.type.getText(sf);
      if (t === "const") counts.asConst++;
      else {
        counts.as++;
        perFile.as[rel] = (perFile.as[rel] || 0) + 1;
        if (ts.isAsExpression(node.expression) && node.expression.type.kind === ts.SyntaxKind.UnknownKeyword) {
          counts.asUnknownAs++;
          perFile.asUnknownAs.push(`${rel}:${lineOf(sf, node.getStart(sf))}\t${lines[lineOf(sf, node.getStart(sf)) - 1].trim().slice(0, 140)}`);
        }
      }
    }
    if (ts.isNonNullExpression(node)) {
      counts.nonNull++;
      perFile.nonNull[rel] = (perFile.nonNull[rel] || 0) + 1;
    }
    if (ts.isCatchClause(node)) {
      counts.catches++;
      const body = node.block;
      const bodyText = body.getText(sf);
      const stmts = body.statements;
      const hasComment = /\/\/|\/\*/.test(bodyText);
      const logs = /console\.|report[A-Z]\w*\(|Sentry|captureException|captureMessage|logError|warn\(|showToast|toast|setError|onError|throw /.test(bodyText);
      const empty = stmts.length === 0;
      if (empty) counts.catchEmpty++;
      if (!logs) {
        counts.catchSilent++;
        // classify the try body
        const tryStmt = node.parent;
        const tryText = tryStmt.tryBlock.getText(sf);
        const tryKind = /JSON\.parse/.test(tryText)
          ? "json"
          : /await\s/.test(tryText)
            ? "await"
            : /new URL|decodeURI|encodeURI/.test(tryText)
              ? "url"
              : "sync";
        catchRows.push(
          `${rel}:${lineOf(sf, node.getStart(sf))}\t${tryKind}\t${empty ? "empty" : "stmts"}\t${hasComment ? "commented" : "uncommented"}\t${bodyText.replace(/\s+/g, " ").slice(0, 100)}\t|| try: ${tryText.replace(/\s+/g, " ").slice(0, 120)}`
        );
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
}

const top = (obj, n) =>
  Object.entries(obj)
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([f, c]) => `  ${c}\t${f}`)
    .join("\n");

fs.writeFileSync(path.join(outDir, "ts_functions.tsv"), funcs.map((r) => r.join("\t")).join("\n") + "\n");
fs.writeFileSync(path.join(outDir, "ts_catches.tsv"), catchRows.join("\n") + "\n");
fs.writeFileSync(path.join(outDir, "ts_eslint_disable.tsv"), eslintRows.join("\n") + "\n");
fs.writeFileSync(path.join(outDir, "ts_any.tsv"), anyRows.join("\n") + "\n");
fs.writeFileSync(
  path.join(outDir, "ts_typing.txt"),
  [
    `files: ${files.length}`,
    `counts: ${JSON.stringify(counts)}`,
    `any by file:\n${top(perFile.any, 20)}`,
    `as (non-const) by file:\n${top(perFile.as, 25)}`,
    `non-null ! by file:\n${top(perFile.nonNull, 25)}`,
    `as unknown as:\n${perFile.asUnknownAs.join("\n")}`,
  ].join("\n") + "\n"
);
console.log(JSON.stringify(counts), "functions", funcs.length);
