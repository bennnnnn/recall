// Mobile it()/test() callbacks with no expect(...) and no helper that obviously asserts.
const ts = require(process.argv[2] + "/node_modules/typescript");
const fs = require("fs"); const path = require("path");
const root = process.argv[2];
function walk(dir, out) { for (const e of fs.readdirSync(dir, { withFileTypes: true })) { if (e.name === "node_modules" || e.name.startsWith(".")) continue; const p = path.join(dir, e.name); if (e.isDirectory()) walk(p, out); else if (/\.test\.tsx?$/.test(e.name)) out.push(p); } return out; }
let total = 0; const none = [];
for (const f of walk(root, [])) {
  const sf = ts.createSourceFile(f, fs.readFileSync(f, "utf8"), ts.ScriptTarget.Latest, true);
  (function visit(n) {
    if (ts.isCallExpression(n)) {
      const callee = n.expression.getText(sf);
      if (/^(it|test)(\.each\(.*\))?$/s.test(callee) || /^(it|test)\.each/.test(callee)) {
        const fn = n.arguments[n.arguments.length - 1];
        if (fn && (ts.isArrowFunction(fn) || ts.isFunctionExpression(fn))) {
          total++;
          const body = fn.body.getText(sf);
          if (!/expect\(|expect\.|assert|toThrow|\bcheck[A-Z]\w*\(|\bexpect[A-Z]\w*\(|\bverify\w*\(/.test(body) && body.trim() !== "{}") none.push(`${path.relative(root, f)}:${sf.getLineAndCharacterOfPosition(n.getStart()).line + 1}`);
        }
      }
    }
    ts.forEachChild(n, visit);
  })(sf);
}
console.log("mobile test callbacks:", total, "without expect/assert:", none.length);
console.log(none.slice(0, 30).join("\n"));
