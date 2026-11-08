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

/**
 * MainActivity.kt with the call added: in an onNewIntent it already has, else in one this
 * adds. Applying it again changes nothing.
 */
function addOpenedDocumentHook(source) {
  if (source.includes(CALL)) return source;
  const existing = /override fun onNewIntent\((\w+): Intent\??\)\s*\{\n/.exec(source);
  if (existing) {
    return source.replace(existing[0], `${existing[0]}    ${CALL}(this, ${existing[1]})\n`);
  }
  const declaration = /class MainActivity\s*:\s*ReactActivity\(\)\s*\{\n/.exec(source);
  if (!declaration) throw new Error("withOpenedDocumentIntent: MainActivity.kt has no `class MainActivity : ReactActivity() {`");
  const imported = /^import android\.content\.Intent$/m.test(source)
    ? source
    : source.replace(/^(package [\w.]+\n)/, "$1\nimport android.content.Intent\n");
  return imported.replace(declaration[0], `${declaration[0]}${METHOD}\n`);
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
