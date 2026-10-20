// Longest functions/components in phone production code (TypeScript compiler API).
const ts = require("/home/user/recall-audit/apps/mobile/node_modules/typescript");
const fs = require("fs"), path = require("path");
const ROOT = "/home/user/recall-audit/apps/mobile";
const DIRS = ["app", "components", "contexts", "features", "hooks", "lib", "ui"];
const rows = [];
function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) { if (!["__tests__", "vendor", "node_modules"].includes(e.name)) walk(p); continue; }
    if (!/\.(ts|tsx)$/.test(e.name) || /\.d\.ts$|\.generated\.ts$/.test(e.name)) continue;
    const src = fs.readFileSync(p, "utf8");
    const sf = ts.createSourceFile(p, src, ts.ScriptTarget.Latest, true, e.name.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
    const visit = (node) => {
      let name = null;
      if (ts.isFunctionDeclaration(node) && node.name) name = node.name.text;
      else if ((ts.isArrowFunction(node) || ts.isFunctionExpression(node)) && ts.isVariableDeclaration(node.parent) && ts.isIdentifier(node.parent.name)) name = node.parent.name.text;
      else if (ts.isMethodDeclaration(node) && node.name && ts.isIdentifier(node.name)) name = node.name.text;
      if (name) {
        const a = sf.getLineAndCharacterOfPosition(node.getStart()).line, b = sf.getLineAndCharacterOfPosition(node.getEnd()).line;
        rows.push([b - a + 1, `${path.relative(ROOT, p)}:${a + 1} ${name}`]);
      }
      ts.forEachChild(node, visit);
    };
    visit(sf);
  }
}
DIRS.forEach((d) => walk(path.join(ROOT, d)));
rows.sort((x, y) => y[0] - x[0]);
console.log(`functions: ${rows.length} over 50: ${rows.filter(r => r[0] > 50).length} over 100: ${rows.filter(r => r[0] > 100).length}`);
rows.slice(0, 25).forEach((r) => console.log(r[0], r[1]));
