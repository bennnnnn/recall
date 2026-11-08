package expo.modules.recallopeneddocument

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Parcelable
import android.provider.OpenableColumns
import android.provider.Settings

/**
 * The PDF another app handed Recall, until the app takes it: Open with (ACTION_VIEW, the URI in
 * the intent's data) and Share (ACTION_SEND, the URI in EXTRA_STREAM, which React Native's
 * Linking never reads). Only the newest is kept. The activity listener fills it, the module
 * hands it to JS (features/attachments/model/androidOpenedDocuments.ts). Nothing here may throw
 * into the activity: any app can send Recall a malformed intent.
 */
internal object OpenedDocuments {
  private const val PREFERENCES = "recall_opened_document"
  private const val HANDLED_LAUNCH = "handled_launch"

  private var pending: Uri? = null

  /** Set while the module is alive: tells JS a document is waiting. */
  @Volatile
  var onArrival: (() -> Unit)? = null

  /** The intent MainActivity was created with: taken once per launch (LaunchMarkers). */
  fun receiveLaunch(context: Context, intent: Intent, taskId: Int) {
    val uri = documentUri(intent) ?: return
    val isNew = runCatching {
      LaunchMarkers(preferencesStore(context)).isNew(bootCount(context), taskId, uri.toString())
    }.getOrDefault(true)
    if (isNew) hold(context, uri)
  }

  /** An intent the running activity was handed (onNewIntent): always a new one. */
  fun receive(context: Context, intent: Intent?) {
    val uri = intent?.let(::documentUri) ?: return
    hold(context, uri)
  }

  /** The waiting document as `{ uri, name, size, type }`, once; null when there is none. */
  fun take(context: Context?): Map<String, Any?>? {
    val uri = synchronized(this) { pending.also { pending = null } } ?: return null
    val details = context?.let { describe(it, uri) }
    return mapOf(
      "uri" to uri.toString(),
      "name" to details?.name,
      "size" to details?.size,
      "type" to details?.type,
    )
  }

  private fun hold(context: Context, uri: Uri) {
    if (!isForeignContent(context, uri)) return
    synchronized(this) { pending = uri }
    runCatching { onArrival?.invoke() }
  }

  private fun documentUri(intent: Intent): Uri? = runCatching {
    when (intent.action) {
      Intent.ACTION_VIEW -> intent.data
      Intent.ACTION_SEND -> streamOf(intent)
      else -> null
    }
  }.getOrNull()

  /** EXTRA_STREAM when it is a Uri: another Parcelable, or one that will not unparcel, is no document. */
  private fun streamOf(intent: Intent): Uri? {
    val stream: Parcelable? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
      intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
    } else {
      legacyStreamOf(intent)
    }
    return stream as? Uri
  }

  @Suppress("DEPRECATION")
  private fun legacyStreamOf(intent: Intent): Parcelable? = intent.getParcelableExtra(Intent.EXTRA_STREAM)

  /**
   * A `content:` URI another app's provider serves. Not a `file:` path, and not Recall's own
   * provider: either would let another app have Recall read, and attach, Recall's private files.
   * A lookup that fails refuses it.
   */
  // resolveContentProvider(String, Int) is deprecated from API 33 in favour of a flags object; it still works.
  @Suppress("DEPRECATION")
  private fun isForeignContent(context: Context, uri: Uri): Boolean {
    if (uri.scheme != "content") return false
    // ContentResolver drops a "<userId>@" prefix before it looks the provider up.
    val authority = uri.authority?.substringAfterLast('@') ?: return false
    val provider = runCatching { context.packageManager.resolveContentProvider(authority, 0) }
      .getOrElse { return false }
    return provider?.packageName != context.packageName
  }

  private class Details(val name: String?, val size: Long?, val type: String?)

  /**
   * The name the other app gives the file ("Lease.pdf"), its size and its type. Asked here, off
   * the JS thread: expo-file-system measures a provider that gives no size by reading the whole
   * file, on whichever thread asks.
   */
  private fun describe(context: Context, uri: Uri): Details {
    val resolver = context.contentResolver
    val type = runCatching { resolver.getType(uri) }.getOrNull()
    val columns = arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE)
    return runCatching {
      resolver.query(uri, columns, null, null, null)?.use { cursor ->
        if (!cursor.moveToFirst()) return@use null
        val nameColumn = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
        val sizeColumn = cursor.getColumnIndex(OpenableColumns.SIZE)
        Details(
          name = if (nameColumn >= 0 && !cursor.isNull(nameColumn)) cursor.getString(nameColumn) else null,
          size = if (sizeColumn >= 0 && !cursor.isNull(sizeColumn)) cursor.getLong(sizeColumn) else null,
          type = type,
        )
      }
    }.getOrNull() ?: Details(null, null, type)
  }

  private fun bootCount(context: Context): Int =
    runCatching { Settings.Global.getInt(context.contentResolver, Settings.Global.BOOT_COUNT) }.getOrDefault(-1)

  private fun preferencesStore(context: Context): LaunchMarkers.Store {
    val preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
    return object : LaunchMarkers.Store {
      override fun read(): String? = preferences.getString(HANDLED_LAUNCH, null)

      // apply(): the write is on disk before the activity stops, which a process kill comes after.
      override fun write(marker: String) = preferences.edit().putString(HANDLED_LAUNCH, marker).apply()
    }
  }
}
