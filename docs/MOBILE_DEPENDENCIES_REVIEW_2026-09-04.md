# Mobile dependency security cleanup — 2026-09-04

The mobile lockfile contained two Browserslist alerts and one URI decoder alert.
This update pins Browserslist 4.28.7 and
decode-uri-component 0.5.0. The browser data packages update to satisfy the patched
Browserslist release; Expo and React Native versions remain the same.

Advisories:
- [Browserslist custom statistics handling](https://github.com/browserslist/browserslist/security/advisories/GHSA-73wf-gq98-2v4g)
- [Browserslist cache growth](https://github.com/browserslist/browserslist/security/advisories/GHSA-c83g-rgw3-j3cx)
- [URI decoder malformed-input denial of service](https://github.com/advisories/GHSA-vcc3-ghjq-m6fr)

Expo Router currently loads query-string 7, whose decoder import expects a
CommonJS function. The decoder's patched release uses ESM. A two-line pnpm patch
changes only its module type and export declaration, preserving the complete
upstream security fix. Its installed algorithm was verified identical to the npm
release after normalizing that export. The patch and removal condition are
documented in `apps/mobile/patches/README.md`.

Validation used a fresh isolated dependency installation with pnpm 9.15.9 and the
frozen lockfile. The package audit reported zero vulnerabilities. All 2,547 tests
across 291 suites passed, including the actual Expo Router → query-string → decoder
chain with Unicode, raw/encoded plus signs, round trips, and malformed bytes. The
old decoder exceeded a three-second bound on the malformed-input case; the patched
chain completes within the regression test's bounded subprocess.

TypeScript and ESLint passed. Changed files have no warnings; 146 existing lint
warnings remain elsewhere. Production Metro exports completed for iOS, Android,
and web. These are build checks, not physical-device testing. CI results are
recorded in the PR. Repository dependency alerts clear after the fix reaches the
default branch and GitHub refreshes its dependency graph.
