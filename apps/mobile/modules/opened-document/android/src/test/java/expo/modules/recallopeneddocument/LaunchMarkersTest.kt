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
  fun handsALaunchOverAgainUntilRecallHasHandledIt() {
    val store = MemoryStore()
    val launch = LaunchMarkers.of(bootCount = 7, taskId = 120, uri = lease)
    assertFalse(LaunchMarkers(store).isHandled(launch))
    // The process died while the file waited for sign-in: the next launch hands it over again.
    assertFalse(LaunchMarkers(store).isHandled(launch))
    LaunchMarkers(store).markHandled(launch)
    // Then a font size change or a return after a process death carries it in vain.
    assertTrue(LaunchMarkers(store).isHandled(launch))
  }

  @Test
  fun takesTheSameFileSharedAgainOnceItsTaskIsGone() {
    val store = MemoryStore()
    LaunchMarkers(store).markHandled(LaunchMarkers.of(bootCount = 7, taskId = 120, uri = lease))
    assertFalse(LaunchMarkers(store).isHandled(LaunchMarkers.of(bootCount = 7, taskId = 121, uri = lease)))
  }

  @Test
  fun takesALaunchAfterTheDeviceRestartsEvenWithATaskIdUsedBefore() {
    val store = MemoryStore()
    LaunchMarkers(store).markHandled(LaunchMarkers.of(bootCount = 7, taskId = 120, uri = lease))
    assertFalse(LaunchMarkers(store).isHandled(LaunchMarkers.of(bootCount = 8, taskId = 120, uri = lease)))
  }

  @Test
  fun takesAnotherFileThatStartsTheSameTask() {
    val store = MemoryStore()
    LaunchMarkers(store).markHandled(LaunchMarkers.of(bootCount = 7, taskId = 120, uri = lease))
    assertFalse(LaunchMarkers(store).isHandled(LaunchMarkers.of(bootCount = 7, taskId = 120, uri = invoice)))
  }
}
