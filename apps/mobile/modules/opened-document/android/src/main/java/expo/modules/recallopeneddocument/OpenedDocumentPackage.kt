package expo.modules.recallopeneddocument

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.os.Bundle
import expo.modules.core.interfaces.Package
import expo.modules.core.interfaces.ReactActivityLifecycleListener

/** Hears the intent MainActivity is created with (autolinked by its name). */
class OpenedDocumentPackage : Package {
  override fun createReactActivityLifecycleListeners(activityContext: Context?): List<ReactActivityLifecycleListener> {
    return listOf(OpenedDocumentActivityListener())
  }
}

/**
 * Expo calls `onCreate` at once, even while it delays the app's load. A new intent is read by
 * MainActivity itself (OpenedDocumentIntents): Expo hands one that comes while the app loads to
 * no listener.
 */
private class OpenedDocumentActivityListener : ReactActivityLifecycleListener {
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
}
