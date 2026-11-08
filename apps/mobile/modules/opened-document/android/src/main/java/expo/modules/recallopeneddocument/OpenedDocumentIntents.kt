package expo.modules.recallopeneddocument

import android.content.Context
import android.content.Intent

/**
 * MainActivity hands every new intent here before anything else sees it
 * (plugins/withOpenedDocumentIntent.js). Expo's ReactActivityDelegateWrapper drops a new intent
 * that comes while the app is still loading, without telling its activity listeners, and a
 * release build loads late (expo-updates): a PDF shared to a Recall whose process had died
 * arrives exactly then.
 */
object OpenedDocumentIntents {
  @JvmStatic
  fun onNewIntent(context: Context, intent: Intent?) {
    runCatching { OpenedDocuments.receive(context, intent) }
  }
}
