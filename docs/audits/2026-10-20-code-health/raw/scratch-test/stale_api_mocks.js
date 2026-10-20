// Keys that test factories give the mocked `api` object, versus the keys the real
// `api` object (lib/api.ts spread of feature slices) has. Prints mock keys that do
// not exist on the real object (stale or invented methods).
const ts = require(process.argv[2] + "/node_modules/typescript");
const fs = require("fs");
const path = require("path");
const root = process.argv[2];

function parse(file) {
  return ts.createSourceFile(file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true);
}
function objectKeys(obj) {
  const keys = [];
  for (const p of obj.properties) {
    if (p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name))) keys.push(p.name.text);
  }
  return keys;
}
// Real keys: find `export const <name>Api = {...}` in the slice files.
const slices = {
  accountApi: "features/account/api.ts", analyticsApi: "lib/api/analytics.ts", chatsApi: "features/chat/api.ts",
  memoriesApi: "features/memory/api.ts", homeApi: "features/home/api.ts", searchApi: "features/search/api.ts",
  discoverApi: "lib/api/discover.ts", todosApi: "features/todos/api.ts", pushApi: "lib/api/push.ts",
  attachmentsApi: "features/attachments/api.ts", imagesApi: "features/images/api.ts", speechApi: "features/speech/api.ts",
  scanApi: "lib/api/scan.ts",
};
const real = new Set();
for (const [name, rel] of Object.entries(slices)) {
  const sf = parse(path.join(root, rel));
  let found = false;
  ts.forEachChild(sf, function visit(node) {
    if (ts.isVariableDeclaration(node) && node.name.getText() === name && node.initializer) {
      let init = node.initializer;
      while (init && (ts.isAsExpression(init) || ts.isSatisfiesExpression?.(init) || ts.isParenthesizedExpression(init))) init = init.expression;
      if (ts.isObjectLiteralExpression(init)) { objectKeys(init).forEach((k) => real.add(k)); found = true; }
    }
    ts.forEachChild(node, visit);
  });
  if (!found) console.error("could not read", name, rel);
}
// Mock keys: jest.mock("@/lib/api", () => ({ api: { ... } }))
function walk(dir, out) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name === "node_modules" || e.name.startsWith(".")) continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, out); else if (/\.test\.tsx?$/.test(e.name)) out.push(p);
  }
  return out;
}
const stale = {};
let files = 0, mockKeys = 0;
for (const f of walk(root, [])) {
  const sf = parse(f);
  ts.forEachChild(sf, function visit(node) {
    if (ts.isCallExpression(node) && node.expression.getText() === "jest.mock" && node.arguments.length >= 2 &&
        ts.isStringLiteral(node.arguments[0]) && node.arguments[0].text === "@/lib/api") {
      files++;
      const fn = node.arguments[1];
      // find object literal property `api: {...}` anywhere in the factory
      (function find(n) {
        if (ts.isPropertyAssignment(n) && n.name.getText() === "api" && ts.isObjectLiteralExpression(n.initializer)) {
          for (const k of objectKeys(n.initializer)) {
            mockKeys++;
            if (!real.has(k)) (stale[path.relative(root, f)] ||= []).push(k);
          }
        }
        ts.forEachChild(n, find);
      })(fn);
    }
    ts.forEachChild(node, visit);
  });
}
console.log("real api keys:", real.size, "| files mocking @/lib/api:", files, "| mocked api keys:", mockKeys);
const entries = Object.entries(stale);
console.log("mock keys absent from the real api object:", entries.reduce((a, [, v]) => a + v.length, 0), "in", entries.length, "files");
for (const [f, keys] of entries) console.log("  ", f, "->", keys.join(", "));
