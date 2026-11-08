package expo.modules.recallcallaudio

import android.content.Context
import android.media.AudioDeviceCallback
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import expo.modules.kotlin.functions.Queues
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

/**
 * Where live talk's voice plays on Android.
 *
 * react-native-webrtc plays the call as a call (USAGE_VOICE_COMMUNICATION) and never sets the
 * audio mode or the output device, and Android sends a call's voice to the earpiece by default:
 * with the phone in the hand it was barely audible. During a call this puts the phone in
 * communication mode (the call's echo canceller and volume keys) and plays through a headset
 * the user has connected, else the loudspeaker; a headset that connects or leaves mid-call
 * takes the voice with it. When the call ends the route and the mode are given back.
 */
class CallAudioModule : Module() {
  /** The call's audio manager, held from start to stop: null when no call is routed. */
  private var callManager: AudioManager? = null
  private var modeBefore = AudioManager.MODE_NORMAL
  private var speakerBefore = false
  private val mainHandler = Handler(Looper.getMainLooper())

  private val deviceChanges = object : AudioDeviceCallback() {
    override fun onAudioDevicesAdded(addedDevices: Array<out AudioDeviceInfo>?) = reroute()

    override fun onAudioDevicesRemoved(removedDevices: Array<out AudioDeviceInfo>?) = reroute()
  }

  override fun definition() = ModuleDefinition {
    Name("RecallCallAudio")

    // On the main thread, one after another: a quick hang-up and redial keep their order.
    AsyncFunction("startAsync") {
      start()
    }.runOnQueue(Queues.MAIN)

    AsyncFunction("stopAsync") {
      stop()
    }.runOnQueue(Queues.MAIN)

    // A reload or teardown mid-call must not leave the phone in communication mode.
    OnDestroy {
      stop()
    }
  }

  private fun start() {
    val manager = callManager
      ?: (appContext.reactContext?.getSystemService(Context.AUDIO_SERVICE) as? AudioManager)
      ?: return
    if (callManager == null) {
      callManager = manager
      modeBefore = manager.mode
      @Suppress("DEPRECATION")
      speakerBefore = manager.isSpeakerphoneOn
      manager.registerAudioDeviceCallback(deviceChanges, mainHandler)
    }
    manager.mode = AudioManager.MODE_IN_COMMUNICATION
    route(manager)
  }

  private fun stop() {
    val manager = callManager ?: return
    callManager = null
    manager.unregisterAudioDeviceCallback(deviceChanges)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
      manager.clearCommunicationDevice()
    } else {
      @Suppress("DEPRECATION")
      manager.isSpeakerphoneOn = speakerBefore
    }
    manager.mode = modeBefore
  }

  private fun reroute() {
    callManager?.let(::route)
  }

  private fun route(manager: AudioManager) {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
      val devices = manager.availableCommunicationDevices
      val chosen = CALL_DEVICES.firstNotNullOfOrNull { type -> devices.firstOrNull { it.type == type } } ?: return
      if (manager.communicationDevice?.id != chosen.id) manager.setCommunicationDevice(chosen)
    } else {
      // Before Android 12 a wired or USB headset takes a call by itself; else the loudspeaker.
      val outputs = manager.getDevices(AudioManager.GET_DEVICES_OUTPUTS)
      @Suppress("DEPRECATION")
      manager.isSpeakerphoneOn = outputs.none { it.type in WIRED_HEADSETS }
    }
  }

  private companion object {
    val WIRED_HEADSETS = setOf(
      AudioDeviceInfo.TYPE_WIRED_HEADSET,
      AudioDeviceInfo.TYPE_WIRED_HEADPHONES,
      AudioDeviceInfo.TYPE_USB_HEADSET
    )

    /** Who hears the call, the first one connected: a headset the user put on, else the loudspeaker. */
    val CALL_DEVICES = listOf(
      AudioDeviceInfo.TYPE_BLE_HEADSET,
      AudioDeviceInfo.TYPE_BLUETOOTH_SCO,
      AudioDeviceInfo.TYPE_HEARING_AID,
      AudioDeviceInfo.TYPE_USB_HEADSET,
      AudioDeviceInfo.TYPE_WIRED_HEADSET,
      AudioDeviceInfo.TYPE_WIRED_HEADPHONES,
      AudioDeviceInfo.TYPE_BUILTIN_SPEAKER
    )
  }
}
