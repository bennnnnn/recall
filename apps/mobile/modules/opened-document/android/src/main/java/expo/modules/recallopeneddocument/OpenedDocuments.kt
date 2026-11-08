package expo.modules.recallopeneddocument

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.OpenableColumns

/**
 * The PDF another app handed Recall, until the app takes it: Open with (ACTION_VIEW, the URI in
 * the intent's data) and Share (ACTION_SEND, the URI in EXTRA_STREAM, which React Native's
 * Linking never reads). Only the newest is kept. The activity listener fills it, the module
 * hands it to JS (features/attachments/model/androidOpenedDocuments.ts).
 */
internal object OpenedDocuments {
  private var pending: Uri? = null

  /** Set while the module is alive: tells JS a document is waiting. */
  @Volatile
  var onArrival: (() -> Unit)? = null

  fun receive(context: Context, intent: Intent?) {
    val uri = intent?.let(::documentUri) ?: return
    if (!isForeignContent(context, uri)) return
    synchronized(this) { pending = uri }
    onArrival?.invoke()
  }

  /** The waiting document as `{ uri, name }`, once; null when there is none. */
  fun take(context: Context?): Map<String, Any?>? {
    val uri = synchronized(this) { pending.also { pending = null } } ?: return null
    return mapOf("uri" to uri.toString(), "name" to context?.let { displayName(it, uri) })
  }

  private fun documentUri(intent: Intent): Uri? = when (intent.action) {
    Intent.ACTION_VIEW -> intent.data
    Intent.ACTION_SEND -> streamOf(intent)
    else -> null
  }

  private fun streamOf(intent: Intent): Uri? =
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
      intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
    } else {
      legacyStreamOf(intent)
    }

  @Suppress("DEPRECATION")
  private fun legacyStreamOf(intent: Intent): Uri? = intent.getParcelableExtra(Intent.EXTRA_STREAM)

  /**
   * A `content:` URI another app's provider serves. Not a `file:` path, and not Recall's own
   * provider: either would let another app have Recall read, and attach, Recall's private files.
   */
  // resolveContentProvider(String, Int) is deprecated from API 33 in favour of a flags object; it still works.
  @Suppress("DEPRECATION")
  private fun isForeignContent(context: Context, uri: Uri): Boolean {
    if (uri.scheme != "content") return false
    // ContentResolver drops a "<userId>@" prefix before it looks the provider up.
    val authority = uri.authority?.substringAfterLast('@') ?: return false
    val provider = runCatching { context.packageManager.resolveContentProvider(authority, 0) }.getOrNull()
    return provider?.packageName != context.packageName
  }

  /** The name the other app gives the file ("Lease.pdf"); its URI rarely carries one. */
  private fun displayName(context: Context, uri: Uri): String? = runCatching {
    context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
      val column = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
      if (column >= 0 && cursor.moveToFirst()) cursor.getString(column) else null
    }
  }.getOrNull()
}
