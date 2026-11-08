# Dependency compatibility patches

`react-native-vision-camera-mlkit@2.0.1.patch` lets the iOS app build with barcode scanning
off (`app.json` sets `barcodeScanning: false`). Two bridge files use the barcode types without
the `MLKIT_BARCODE_SCANNING` guard the library puts on every other barcode file, so Swift fails
with "cannot find type 'BarcodeScanningOptions'". The patch adds that guard and changes nothing
else. Remove it when the library guards those files itself.

The existing draggable-flatlist patch is separate and remains unchanged.

`react-native-gesture-handler@3.3.0.patch` stops Android crashing when a text field is tapped
inside the chat drawer's pan (`features/chat/drawer/DrawerShell.tsx`). The text field asks its
parents not to intercept, so gesture-handler cancels the pan. Cancelling first sends
`onTouchesCancelled`, and the pan's handler calls `manager.fail()` there, which ends the
gesture and detaches it. The cancel then went on with a detached handler and threw "Manually
handled gesture had not been assigned to any detector" (Galaxy S23, 2026-11-07). The patch adds
the check 3.4.0 ships: after the pointers are cancelled, a gesture its callback already ended
is left as it is. Remove it when Expo's SDK moves to gesture-handler 3.4 or later.
