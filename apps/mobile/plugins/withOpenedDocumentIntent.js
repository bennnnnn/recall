const { withMainActivity } = require("expo/config-plugins");

/** The call MainActivity makes with every new intent (modules/opened-document). */
const CALL = "expo.modules.recallopeneddocument.OpenedDocumentIntents.onNewIntent";

const METHOD = `
  /**
   * Every intent Recall is handed while it runs goes to modules/opened-document first: a PDF
   * shared while the app is still loading (expo-updates delays the load) never reaches the
   * activity's listeners, which Expo calls only once it has loaded.
   */
  override fun onNewIntent(intent: Intent) {
    ${CALL}(this, intent)
    super.onNewIntent(intent)
  }
`;

/** An onNewIntent with a block body, its parameter named; anything after its brace on that line kept. */
const EXISTING = /override fun onNewIntent\(\s*(\w+)\s*:\s*(?:android\.content\.)?Intent\??\s*\)\s*(?::\s*Unit\s*)?\{[^\n]*\n/;

/** MainActivity.kt with `import android.content.Intent`: after its package line, or first. */
function withIntentImport(source) {
  if (/^import android\.content\.(?:Intent|\*)\s*$/m.test(source)) return source;
  const packageLine = /^package [\w.]+[^\n]*\n/m.exec(source);
  if (!packageLine) return `import android.content.Intent\n${source}`;
  const end = packageLine.index + packageLine[0].length;
  return `${source.slice(0, end)}\nimport android.content.Intent\n${source.slice(end)}`;
}

/**
 * MainActivity.kt with the call added: in an onNewIntent it already has, else in one this
 * adds. Applying it again changes nothing. An onNewIntent it cannot join (an expression body,
 * an annotated parameter) fails the prebuild, rather than a second one being added.
 */
function addOpenedDocumentHook(source) {
  if (source.includes(CALL)) return source;
  const existing = EXISTING.exec(source);
  if (existing) {
    return source.replace(existing[0], `${existing[0]}    ${CALL}(this, ${existing[1]})\n`);
  }
  if (/\bfun onNewIntent\s*\(/.test(source)) {
    throw new Error(
      `withOpenedDocumentIntent: MainActivity.kt has an onNewIntent the plugin cannot join; give it a block body \`override fun onNewIntent(intent: Intent) {\` that calls ${CALL}(this, intent)`,
    );
  }
  const declaration = /class MainActivity\s*:\s*ReactActivity\(\)\s*\{[^\n]*\n/.exec(source);
  if (!declaration) throw new Error("withOpenedDocumentIntent: MainActivity.kt has no `class MainActivity : ReactActivity() {`");
  return withIntentImport(source).replace(declaration[0], `${declaration[0]}${METHOD}\n`);
}

/** Android: MainActivity hands each new intent to the opened-document module before Expo's wrapper sees it. */
function withOpenedDocumentIntent(config) {
  return withMainActivity(config, (cfg) => {
    if (cfg.modResults.language !== "kt") {
      throw new Error("withOpenedDocumentIntent: MainActivity must be Kotlin");
    }
    cfg.modResults.contents = addOpenedDocumentHook(cfg.modResults.contents);
    return cfg;
  });
}

module.exports = withOpenedDocumentIntent;
module.exports.addOpenedDocumentHook = addOpenedDocumentHook;
