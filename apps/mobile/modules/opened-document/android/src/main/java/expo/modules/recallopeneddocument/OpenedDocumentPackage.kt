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
    runCatching {
      val intent = activity.intent ?: return
      // Reopened from Recents: the intent the task began with, handed over then.
      if ((intent.flags and Intent.FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY) != 0) return
      // A configuration change or a return after the process died carries it too, and
      // savedInstanceState never tells (MainActivity passes null): LaunchMarkers does.
      OpenedDocuments.receiveLaunch(activity, intent, activity.taskId)
    }
  }

  override fun onNewIntent(intent: Intent?): Boolean {
    activityContext?.let { context -> runCatching { OpenedDocuments.receive(context, intent) } }
    // React Native still reads the intent (Linking); Expo Router keeps a content: URL off the routes.
    return false
  }
}
