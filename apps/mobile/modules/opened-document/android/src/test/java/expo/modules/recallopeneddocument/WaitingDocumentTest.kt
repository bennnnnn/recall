package expo.modules.recallopeneddocument

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class WaitingDocumentTest {
  private val lease = "content://com.android.providers.downloads.documents/document/42"
  private val invoice = "content://com.whatsapp.provider.media/item/9"
  private val leaseLaunch = LaunchMarkers.of(bootCount = 7, taskId = 120, uri = lease)

  @Test
  fun marksALaunchsFileHandledWhenAShareReplacesItBeforeJsTookIt() {
    // Lease.pdf launched Recall and its process died; Invoice.pdf is shared to the dead process.
    val replacement = WaitingDocument(lease, leaseLaunch).replacedBy(WaitingDocument(invoice, null))
    assertEquals(invoice, replacement.waiting.uri)
    assertNull(replacement.waiting.launch)
    // Else the next font size change or launcher return hands Lease.pdf over again.
    assertEquals(leaseLaunch, replacement.handledLaunch)
  }

  @Test
  fun keepsTheLaunchsNameWhenTheSameFileIsSharedAgain() {
    val replacement = WaitingDocument(lease, leaseLaunch).replacedBy(WaitingDocument(lease, null))
    assertEquals(leaseLaunch, replacement.waiting.launch)
    assertNull(replacement.handledLaunch)
  }

  @Test
  fun keepsALaunchARecreatedActivityHandsOverAgain() {
    val replacement = WaitingDocument(lease, leaseLaunch).replacedBy(WaitingDocument(lease, leaseLaunch))
    assertEquals(leaseLaunch, replacement.waiting.launch)
    assertNull(replacement.handledLaunch)
  }

  @Test
  fun marksNothingWhenTheReplacedFileCameWithANewIntent() {
    val replacement = WaitingDocument(invoice, null).replacedBy(WaitingDocument(lease, null))
    assertEquals(lease, replacement.waiting.uri)
    assertNull(replacement.handledLaunch)
  }
}
