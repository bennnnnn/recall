package expo.modules.recallopeneddocument

/**
 * A document waiting for JS to take it. `launch` names the launch that brought it (LaunchMarkers),
 * null for a new intent.
 */
internal class WaitingDocument(val uri: String, val launch: String?) {
  /** What waits once `next` comes while this one waits, and the launch Recall is then done with. */
  class Replacement(val waiting: WaitingDocument, val handledLaunch: String?)

  /**
   * Only the newest document waits. A launch's document another file replaces is done with: its
   * launch is marked handled, or a recreated activity (a font size change, a return from the
   * launcher) would hand it over again. The same file handed over again keeps its launch's name,
   * so JS can mark it handled once it is done with it.
   */
  fun replacedBy(next: WaitingDocument): Replacement =
    if (next.uri == uri) {
      Replacement(WaitingDocument(next.uri, next.launch ?: launch), null)
    } else {
      Replacement(next, launch)
    }
}
