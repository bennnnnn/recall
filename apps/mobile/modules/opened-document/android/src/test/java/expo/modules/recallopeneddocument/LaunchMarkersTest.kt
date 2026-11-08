package expo.modules.recallopeneddocument

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LaunchMarkersTest {
  /** SharedPreferences, as a new process finds it. */
  private class MemoryStore : LaunchMarkers.Store {
    var marker: String? = null

    override fun read(): String? = marker

    override fun write(marker: String) {
      this.marker = marker
    }
  }

  private val lease = "content://com.android.providers.downloads.documents/document/42"
  private val invoice = "content://com.whatsapp.provider.media/item/9"

  @Test
  fun takesALaunchOnceThroughAConfigurationChangeAndAProcessDeath() {
    val store = MemoryStore()
    assertTrue(LaunchMarkers(store).isNew(bootCount = 7, taskId = 120, uri = lease))
    // The font size changed: MainActivity is created again with the same intent.
    assertFalse(LaunchMarkers(store).isNew(bootCount = 7, taskId = 120, uri = lease))
    // The process died in the background and the user came back from the launcher.
    assertFalse(LaunchMarkers(store).isNew(bootCount = 7, taskId = 120, uri = lease))
  }

  @Test
  fun takesTheSameFileSharedAgainOnceItsTaskIsGone() {
    val store = MemoryStore()
    assertTrue(LaunchMarkers(store).isNew(bootCount = 7, taskId = 120, uri = lease))
    assertTrue(LaunchMarkers(store).isNew(bootCount = 7, taskId = 121, uri = lease))
  }

  @Test
  fun takesALaunchAfterTheDeviceRestartsEvenWithATaskIdUsedBefore() {
    val store = MemoryStore()
    assertTrue(LaunchMarkers(store).isNew(bootCount = 7, taskId = 120, uri = lease))
    assertTrue(LaunchMarkers(store).isNew(bootCount = 8, taskId = 120, uri = lease))
  }

  @Test
  fun takesAnotherFileThatStartsTheSameTask() {
    val store = MemoryStore()
    assertTrue(LaunchMarkers(store).isNew(bootCount = 7, taskId = 120, uri = lease))
    assertTrue(LaunchMarkers(store).isNew(bootCount = 7, taskId = 120, uri = invoice))
    // Only the newest launch is the one a recreated activity can carry.
    assertFalse(LaunchMarkers(store).isNew(bootCount = 7, taskId = 120, uri = invoice))
  }
}
