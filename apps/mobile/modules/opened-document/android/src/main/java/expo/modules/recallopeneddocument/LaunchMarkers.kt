package expo.modules.recallopeneddocument

/**
 * Tells a document another app just handed Recall from the same one handed over again.
 *
 * MainActivity is created anew with the intent its task began with after a configuration change
 * it does not handle (locale, font size, display size) and when its process died in the
 * background and the user comes back (from Recents or the launcher). Expo's MainActivity calls
 * `super.onCreate(null)`, so no saved state marks either one. The launch that brought a document
 * is remembered by the device's boot, the task and the document: the same three again are that
 * launch again. A new share starts a new task (or reaches the running one through onNewIntent),
 * so the same file shared later is still taken.
 */
internal class LaunchMarkers(private val store: Store) {
  interface Store {
    fun read(): String?

    fun write(marker: String)
  }

  /** True for a launch Recall has not handled yet, and it is recorded; false for one seen before. */
  fun isNew(bootCount: Int, taskId: Int, uri: String): Boolean {
    val marker = "$bootCount:$taskId:$uri"
    if (store.read() == marker) return false
    store.write(marker)
    return true
  }
}
