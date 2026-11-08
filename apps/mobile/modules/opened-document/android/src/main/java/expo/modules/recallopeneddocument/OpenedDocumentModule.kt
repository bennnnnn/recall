package expo.modules.recallopeneddocument

import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

/**
 * Hands JS the PDF another app opened or shared in Recall on Android (OpenedDocuments). JS takes
 * the one that launched the app when it starts, and each later one when `onDocument` fires, and
 * says when it has handled a launch's document, so a recreated activity does not hand it again.
 */
class OpenedDocumentModule : Module() {
  private val arrival: () -> Unit = { sendEvent("onDocument") }

  override fun definition() = ModuleDefinition {
    Name("RecallOpenedDocument")

    Events("onDocument")

    OnCreate {
      OpenedDocuments.onArrival = arrival
    }

    // A reload builds the next module before this one is destroyed: leave its listener alone.
    OnDestroy {
      if (OpenedDocuments.onArrival === arrival) OpenedDocuments.onArrival = null
    }

    // Off the main thread: the file's name and size are a query to the app that shared it.
    AsyncFunction("takeDocumentAsync") {
      OpenedDocuments.take(appContext.reactContext)
    }

    AsyncFunction("markLaunchHandledAsync") { launch: String ->
      OpenedDocuments.markLaunchHandled(appContext.reactContext, launch)
    }
  }
}
