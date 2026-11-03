# Dependency compatibility patches

`react-native-vision-camera-mlkit@2.0.1.patch` lets the iOS app build with barcode scanning
off (`app.json` sets `barcodeScanning: false`). Two bridge files use the barcode types without
the `MLKIT_BARCODE_SCANNING` guard the library puts on every other barcode file, so Swift fails
with "cannot find type 'BarcodeScanningOptions'". The patch adds that guard and changes nothing
else. Remove it when the library guards those files itself.

The existing draggable-flatlist patch is separate and remains unchanged.
