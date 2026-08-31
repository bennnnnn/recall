"use strict";

function unavailable() {
  throw new Error("react-native-webrtc is not linked");
}

module.exports = {
  mediaDevices: { getUserMedia: unavailable },
  RTCPeerConnection: function RTCPeerConnection() {
    unavailable();
  },
  RTCSessionDescription: function RTCSessionDescription() {
    unavailable();
  },
};
