// Which mobile test files does neither jest project's testMatch pick up?
const path = require("path");
const fs = require("fs");
const root = process.argv[2];
const mm = require(path.join(root, "node_modules/.pnpm/micromatch@4.0.8/node_modules/micromatch"));
const libMatch = [
  "**/lib/__tests__/**/*.test.ts",
  "**/lib/**/__tests__/**/*.test.ts",
  "**/features/**/__tests__/**/*.test.ts",
  "**/ui/**/__tests__/**/*.test.ts",
  "**/components/**/__tests__/**/*.test.ts",
];
const compMatch = ["**/__tests__/**/*.test.tsx"];
function walk(dir, out) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name === "node_modules" || e.name.startsWith(".")) continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, out);
    else if (/\.(test|spec)\.(ts|tsx|js|jsx)$/.test(e.name)) out.push(p);
  }
  return out;
}
const files = walk(root, []);
let unmatched = [], both = [];
for (const f of files) {
  const a = mm.isMatch(f, libMatch);
  const b = mm.isMatch(f, compMatch);
  if (!a && !b) unmatched.push(path.relative(root, f));
  if (a && b) both.push(path.relative(root, f));
}
console.log("total", files.length, "unmatched", unmatched.length, "both", both.length);
console.log(unmatched.join("\n"));
