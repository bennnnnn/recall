package expo.modules.recallcallaudio

import android.annotation.TargetApi
import android.content.Context
import android.media.AudioAttributes
import android.media.AudioDeviceCallback
import android.media.AudioDeviceInfo
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log
import expo.modules.kotlin.functions.Queues
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import java.util.concurrent.Executor

/**
 * Where live talk's voice plays on Android.
 *
 * react-native-webrtc plays the call as a call (USAGE_VOICE_COMMUNICATION) and never sets the
 * audio mode or the output device, and Android sends a call's voice to the earpiece by default:
 * with the phone in the hand it was barely audible. During a call this puts the phone in
 * communication mode (the call's echo canceller and volume keys), takes audio focus (another
 * app's music pauses rather than play into the mic), and plays through a headset the user has
 * connected, else the loudspeaker. A headset that connects or leaves mid-call takes the voice
 * with it, and the call takes its route again if anything in the app resets the mode
 * (expo-audio's setAudioModeAsync). When the call ends the route and the focus are given back,
 * and the mode is normal again.
 *
 * One route for the app: the JS side counts the calls holding it (features/speech/model/callAudio.ts).
 */
class CallAudioModule : Module() {
  /** The call's audio manager, held from start to stop: null when no call is routed. */
  private var callManager: AudioManager? = null
  private var speakerBefore = false
  private var scoStarted = false
  private var focusRequest: AudioFocusRequest? = null
  private val mainHandler = Handler(Looper.getMainLooper())
  private val onMain = Executor { mainHandler.post(it) }

  private val deviceChanges = object : AudioDeviceCallback() {
    override fun onAudioDevicesAdded(addedDevices: Array<out AudioDeviceInfo>?) = reroute()

    override fun onAudioDevicesRemoved(removedDevices: Array<out AudioDeviceInfo>?) = reroute()
  }

  /** The call keeps the voice even when another app takes focus for a moment (a notification). */
  private val focusChanges = AudioManager.OnAudioFocusChangeListener { }

  /**
   * Android 12+: set back to normal mid-call (expo-audio's setAudioModeAsync does, with the
   * speakerphone), the call takes its mode and its device again. A phone call's own modes
   * (ringing, in call) are left alone.
   */
  private val modeChanges by lazy {
    AudioManager.OnModeChangedListener { mode -> if (mode == AudioManager.MODE_NORMAL) reroute(reassertMode = true) }
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

  @Synchronized
  private fun start() {
    val manager = callManager
      ?: (appContext.reactContext?.getSystemService(Context.AUDIO_SERVICE) as? AudioManager)
      ?: return
    if (callManager == null) {
      callManager = manager
      @Suppress("DEPRECATION")
      speakerBefore = manager.isSpeakerphoneOn
      requestFocus(manager)
      manager.registerAudioDeviceCallback(deviceChanges, mainHandler)
      if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) watchRouteChanges(manager)
    }
    manager.mode = AudioManager.MODE_IN_COMMUNICATION
    route(manager)
  }

  @Synchronized
  private fun stop() {
    val manager = callManager ?: return
    callManager = null
    runCatching {
      manager.unregisterAudioDeviceCallback(deviceChanges)
      if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        unwatchRouteChanges(manager)
        manager.clearCommunicationDevice()
      } else {
        stopSco(manager)
        // A phone call answered mid-session owns the speaker now: leave it as that call set it.
        @Suppress("DEPRECATION")
        if (manager.mode == AudioManager.MODE_IN_COMMUNICATION) manager.isSpeakerphoneOn = speakerBefore
      }
      abandonFocus(manager)
      // Normal, never the mode found at start: that could be another app's call, held for it.
      manager.mode = AudioManager.MODE_NORMAL
    }.onFailure { Log.w(TAG, "Could not give the call's audio route back", it) }
  }

  @Synchronized
  private fun reroute(reassertMode: Boolean = false) {
    val manager = callManager ?: return
    if (reassertMode) manager.mode = AudioManager.MODE_IN_COMMUNICATION
    route(manager)
  }

  /** Never throws: a headset that leaves while it is chosen must not crash the app from a callback. */
  private fun route(manager: AudioManager) {
    runCatching {
      if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) routeToCommunicationDevice(manager) else routeBeforeS(manager)
    }.onFailure { Log.w(TAG, "Could not route the call", it) }
  }

  /** The first connected device that takes the call, down the list to the loudspeaker. */
  @TargetApi(Build.VERSION_CODES.S)
  private fun routeToCommunicationDevice(manager: AudioManager) {
    val devices = manager.availableCommunicationDevices
    for (type in CALL_DEVICES) {
      val device = devices.firstOrNull { it.type == type } ?: continue
      if (manager.communicationDevice?.id == device.id) return
      // A device gone since the list was read throws, or is refused: try the next one.
      if (runCatching { manager.setCommunicationDevice(device) }.getOrDefault(false)) return
    }
  }

  /** Before Android 12: a Bluetooth headset over SCO, a wired or USB one by itself, else the loudspeaker. */
  @Suppress("DEPRECATION")
  private fun routeBeforeS(manager: AudioManager) {
    val outputs = manager.getDevices(AudioManager.GET_DEVICES_OUTPUTS)
    if (outputs.any { it.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO }) {
      manager.isSpeakerphoneOn = false
      if (!scoStarted) {
        manager.startBluetoothSco()
        scoStarted = true
      }
      manager.isBluetoothScoOn = true
      return
    }
    stopSco(manager)
    manager.isSpeakerphoneOn = outputs.none { it.type in WIRED_HEADSETS }
  }

  @Suppress("DEPRECATION")
  private fun stopSco(manager: AudioManager) {
    if (!scoStarted) return
    scoStarted = false
    manager.isBluetoothScoOn = false
    manager.stopBluetoothSco()
  }

  @TargetApi(Build.VERSION_CODES.S)
  private fun watchRouteChanges(manager: AudioManager) {
    manager.addOnModeChangedListener(onMain, modeChanges)
  }

  @TargetApi(Build.VERSION_CODES.S)
  private fun unwatchRouteChanges(manager: AudioManager) {
    manager.removeOnModeChangedListener(modeChanges)
  }

  private fun requestFocus(manager: AudioManager) {
    runCatching {
      if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
        val attributes = AudioAttributes.Builder()
          .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
          .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
          .build()
        val request = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
          .setAudioAttributes(attributes)
          .setOnAudioFocusChangeListener(focusChanges, mainHandler)
          .build()
        focusRequest = request
        manager.requestAudioFocus(request)
      } else {
        @Suppress("DEPRECATION")
        manager.requestAudioFocus(focusChanges, AudioManager.STREAM_VOICE_CALL, AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
      }
    }.onFailure { Log.w(TAG, "Could not take audio focus for the call", it) }
  }

  private fun abandonFocus(manager: AudioManager) {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
      focusRequest?.let(manager::abandonAudioFocusRequest)
      focusRequest = null
    } else {
      @Suppress("DEPRECATION")
      manager.abandonAudioFocus(focusChanges)
    }
  }

  private companion object {
    const val TAG = "RecallCallAudio"

    val WIRED_HEADSETS = setOf(
      AudioDeviceInfo.TYPE_WIRED_HEADSET,
      AudioDeviceInfo.TYPE_WIRED_HEADPHONES,
      AudioDeviceInfo.TYPE_USB_HEADSET,
      AudioDeviceInfo.TYPE_USB_DEVICE
    )

    /** Who hears the call, the first one connected: a headset the user put on, else the loudspeaker. */
    val CALL_DEVICES = listOf(
      AudioDeviceInfo.TYPE_BLE_HEADSET,
      AudioDeviceInfo.TYPE_BLUETOOTH_SCO,
      AudioDeviceInfo.TYPE_HEARING_AID,
      AudioDeviceInfo.TYPE_USB_HEADSET,
      AudioDeviceInfo.TYPE_USB_DEVICE,
      AudioDeviceInfo.TYPE_WIRED_HEADSET,
      AudioDeviceInfo.TYPE_WIRED_HEADPHONES,
      AudioDeviceInfo.TYPE_BUILTIN_SPEAKER
    )
  }
}
