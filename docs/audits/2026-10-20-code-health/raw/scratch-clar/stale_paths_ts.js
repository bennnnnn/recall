// Comments in mobile production code naming a file path that exists nowhere in the repo (read-only).
const fs = require("fs"), path = require("path"), cp = require("child_process");
const REPO = "/home/user/recall-audit";
const root = REPO + "/apps/mobile";
const ts = require(root + "/node_modules/typescript");
const files = cp.execSync(`git -C ${REPO} ls-files`, { encoding: "utf8", maxBuffer: 1 << 26 }).split("\n").filter(Boolean);
const byBase = {};
for (const f of files) (byBase[path.basename(f)] ||= []).push(f);
const exists = (ref) => (byBase[path.basename(ref)] || []).some((f) => f.endsWith(ref));
const DIRS = ["app", "components", "contexts", "features", "hooks", "lib", "ui"];
const PATH = /(?<![\w.`\/-])((?:[\w-]+\/)*[\w-]+\.(?:py|tsx?|md|json|mjs))\b/g;
const out = [];
function walk(d) {
  for (const n of fs.readdirSync(d)) {
    const p = path.join(d, n);
    const st = fs.statSync(p);
    if (st.isDirectory()) { if (!["__tests__", "node_modules", "vendor", "__mocks__"].includes(n)) walk(p); }
    else if (/\.(ts|tsx)$/.test(n) && !/\.test\./.test(n)) {
      const src = fs.readFileSync(p, "utf8");
      const scanner = ts.createScanner(ts.ScriptTarget.Latest, false, n.endsWith(".tsx") ? ts.LanguageVariant.JSX : ts.LanguageVariant.Standard, src);
      let tok;
      while ((tok = scanner.scan()) !== ts.SyntaxKind.EndOfFileToken) {
        if (tok === ts.SyntaxKind.SingleLineCommentTrivia || tok === ts.SyntaxKind.MultiLineCommentTrivia) {
          const text = scanner.getTokenText();
          const start = scanner.getTokenPos();
          for (const m of text.matchAll(PATH)) {
            if (!exists(m[1])) {
              const line = src.slice(0, start + m.index).split("\n").length;
              out.push(`${path.relative(REPO, p)}:${line}\t${m[1]}\t${text.split("\n").find((l) => l.includes(m[1])).trim().slice(0, 110)}`);
            }
          }
        }
      }
    }
  }
}
for (const d of DIRS) walk(path.join(root, d));
console.log(out.length + "\n" + out.join("\n"));
