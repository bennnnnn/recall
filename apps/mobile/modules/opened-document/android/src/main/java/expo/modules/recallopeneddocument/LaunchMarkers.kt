package expo.modules.recallopeneddocument

/**
 * Tells a document another app just handed Recall from the same one handed over again.
 *
 * MainActivity is created anew with the intent its task began with after a configuration change
 * it does not handle (locale, font size, display size) and when its process died in the
 * background and the user comes back (from Recents or the launcher). Expo's MainActivity calls
 * `super.onCreate(null)`, so no saved state marks either one. The launch that brought a document
 * is named by the device's boot, the task and the document, and recorded once Recall has handled
 * the document (taken it into a composer, or dropped it on purpose): the same launch again is
 * then refused. Until then it is handed over again, so a process that dies first loses nothing.
 * A share while the task exists reaches the activity as a new intent, which is never refused, so
 * the same file shared again is still taken.
 */
internal class LaunchMarkers(private val store: Store) {
  interface Store {
    fun read(): String?

    fun write(marker: String)
  }

  /** Recall handled this launch's document already. */
  fun isHandled(marker: String): Boolean = store.read() == marker

  /** Recall has handled this launch's document: a recreated activity carrying it is refused. */
  fun markHandled(marker: String) = store.write(marker)

  companion object {
    fun of(bootCount: Int, taskId: Int, uri: String): String = "$bootCount:$taskId:$uri"
  }
}
