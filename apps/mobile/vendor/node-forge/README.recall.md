Vendored `node-forge` for Expo CLI code signing (`@expo/cli` → `node-forge@1.4.0`).

Upstream has no release past 1.4.0 that rejects extra elements inside the nested
DigestAlgorithm sequence (GHSA-86w9-cpqp-85rv). This copy is the 1.4.0 library
plus the length check from digitalbazaar/forge#1152, and reports version 1.4.1
so Dependabot’s `<= 1.4.0` range clears. The browser bundle and Flash helper
are omitted; Expo loads `lib/index.js`.

Remove when upstream publishes a patched release and Expo adopts it.
