// Find useEffect/useLayoutEffect/useFocusEffect callbacks that register something
// (listener, timer, subscription, socket, player) but return no cleanup.
// Read-only: parses TS/TSX with the TypeScript compiler API.
// Usage: node effect_cleanup.js <mobile_dir>
const path = require("path");
const fs = require("fs");
const mobile = process.argv[2];
const ts = require(path.join(mobile, "node_modules/typescript"));

const DIRS = ["app", "components", "features", "hooks", "contexts", "lib", "ui"];
const REGISTER = /\b(addEventListener|addListener|setInterval|setTimeout|subscribe[A-Za-z]*|on[A-Z][A-Za-z]*Listener|watch[A-Z][A-Za-z]*|new WebSocket|createAudioPlayer|requestAnimationFrame|InteractionManager\.runAfterInteractions|Keyboard\.addListener|Linking\.addEventListener|AppState\.addEventListener|NetInfo\.addEventListener|Dimensions\.addEventListener)\b/;

function walk(dir, out) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    if (name === "node_modules" || name === "__tests__" || name === "vendor") continue;
    const st = fs.statSync(full);
    if (st.isDirectory()) walk(full, out);
    else if (/\.(ts|tsx)$/.test(name) && !/\.test\./.test(name) && !/\.d\.ts$/.test(name)) out.push(full);
  }
  return out;
}

function returnsCleanup(fn) {
  // Arrow with expression body returning a function, or a block with a `return <expr>` at top level
  if (!fn.body) return false;
  if (!ts.isBlock(fn.body)) return true; // expression-bodied effect: returns its value
  let found = false;
  function visit(node) {
    if (found) return;
    if (ts.isFunctionLike(node) && node !== fn) return; // don't descend into nested fns
    if (ts.isReturnStatement(node) && node.expression) found = true;
    ts.forEachChild(node, visit);
  }
  ts.forEachChild(fn.body, visit);
  return found;
}

const files = DIRS.flatMap((d) => (fs.existsSync(path.join(mobile, d)) ? walk(path.join(mobile, d), []) : []));
for (const file of files) {
  const text = fs.readFileSync(file, "utf8");
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, file.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  function visit(node) {
    if (ts.isCallExpression(node)) {
      const callee = node.expression.getText(sf);
      if (/^(React\.)?(useEffect|useLayoutEffect|useFocusEffect)$/.test(callee) && node.arguments.length) {
        let fn = node.arguments[0];
        if (ts.isCallExpression(fn) && /useCallback$/.test(fn.expression.getText(sf)) && fn.arguments.length) fn = fn.arguments[0];
        if (ts.isArrowFunction(fn) || ts.isFunctionExpression(fn)) {
          const bodyText = fn.body.getText(sf);
          const m = bodyText.match(REGISTER);
          if (m && !returnsCleanup(fn)) {
            const { line } = sf.getLineAndCharacterOfPosition(node.getStart(sf));
            console.log(`${path.relative(mobile, file)}:${line + 1}: ${callee} registers ${m[1]} with no returned cleanup`);
          }
        }
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
}
