# Dependency compatibility patches

`decode-uri-component@0.5.1.patch` keeps the upstream security fixes while exposing the
package as CommonJS for Expo Router's `query-string@7` dependency. It changes only
the package module type and export declaration; the decoding algorithm is unchanged.
0.5.0 addressed [GHSA-vcc3-ghjq-m6fr](https://github.com/advisories/GHSA-vcc3-ghjq-m6fr);
0.5.1 addresses [GHSA-qr28-fpjm-wq7f](https://github.com/advisories/GHSA-qr28-fpjm-wq7f)
(0.5.0 rescanned the whole input once per distinct percent-encoded run). Expo Router
ships the decoder in the app bundle, so it is pinned by the `decode-uri-component`
override in `package.json`; a new version needs the override, the `patchedDependencies`
key and this file's name moved together.

Remove this patch when Expo Router supports a query-string version that imports the
decoder's ESM default export. Run the URL dependency regression test
(`lib/__tests__/urlDependencies.test.ts`, which runs `scripts/check-url-dependencies.cjs`)
and Metro exports when updating either package. The test exercises the actual Expo
dependency chain, with a bounded case for each advisory: repeated malformed bytes, and
49,152 distinct runs (about 7 s on 0.5.0, past the test's 5 s limit).

`react-native-vision-camera-mlkit@2.0.1.patch` lets the iOS app build with barcode scanning
off (`app.json` sets `barcodeScanning: false`). Two bridge files use the barcode types without
the `MLKIT_BARCODE_SCANNING` guard the library puts on every other barcode file, so Swift fails
with "cannot find type 'BarcodeScanningOptions'". The patch adds that guard and changes nothing
else. Remove it when the library guards those files itself.

The existing draggable-flatlist patch is separate and remains unchanged.
