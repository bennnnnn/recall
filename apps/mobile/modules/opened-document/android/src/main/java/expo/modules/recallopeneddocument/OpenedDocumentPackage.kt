package expo.modules.recallopeneddocument

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.os.Bundle
import expo.modules.core.interfaces.Package
import expo.modules.core.interfaces.ReactActivityLifecycleListener

/** Hears the intents MainActivity is started and reopened with (autolinked by its name). */
class OpenedDocumentPackage : Package {
  override fun createReactActivityLifecycleListeners(activityContext: Context?): List<ReactActivityLifecycleListener> {
    return listOf(OpenedDocumentActivityListener(activityContext))
  }
}

private class OpenedDocumentActivityListener(private val activityContext: Context?) : ReactActivityLifecycleListener {
  override fun onCreate(activity: Activity?, savedInstanceState: Bundle?) {
    if (activity == null) return
    val intent = activity.intent ?: return
    // A restored activity, or one reopened from Recents, carries the intent its task began with:
    // that file was handed over then, and attaching it again would surprise.
    if (savedInstanceState != null) return
    if ((intent.flags and Intent.FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY) != 0) return
    OpenedDocuments.receive(activity, intent)
  }

  override fun onNewIntent(intent: Intent?): Boolean {
    activityContext?.let { OpenedDocuments.receive(it, intent) }
    // React Native still reads the intent (Linking); Expo Router keeps a content: URL off the routes.
    return false
  }
}
