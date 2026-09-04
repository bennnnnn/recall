# Authentication and session review — September 4, 2026

Scope: Google, Apple and development sign-in; secure credential persistence; startup recovery; token refresh; sign-out; account switching; account-bound background sync.

## Corrected failure cases

- Access and refresh credentials were written separately, and storage errors were silently accepted through an in-memory fallback. Credentials now use one atomic SecureStore record; unavailable storage reports failure. Legacy records migrate without moving credentials into ordinary files.
- A completed native write from an obsolete sign-in could survive a subsequent account change. Serialized writes and session generation checks prevent stale credentials from remaining on disk.
- Refresh requests, retained callbacks and response-body decoding could affect a newer account or restore a signed-out user. The storage, request and provider layers now enforce the originating session.
- Temporary refresh outages were treated as invalid credentials. Network, server and secure-storage failures now preserve the session; definitive authentication rejection signs out consistently across JSON, downloads and streaming requests.
- A startup refresh could replace a newly rotated token with its expired predecessor. Hydration now uses the securely stored current token after validation.
- Startup without a cached profile treated temporary failures as sign-out. It now presents a recoverable Retry screen. Cached first paint remains available, while account settings sync waits for a validated profile.
- A profile edit could supersede startup validation but still release cached preference defaults into background sync. Validation now follows adoption of a full server profile, including recovery after an offline launch or failed edit.
- Sign-out waited for network and cleanup work before removing the account from the UI. UI state and session invalidation now happen immediately; cleanup cannot write an old user's cached profile or preferences back afterward.
- Onboarding used the same fragile keychain fallback despite being a non-secret preference. It now persists through the existing file-preference layer, with migration and ordering guards.
- Refresh rotation consumed the only refresh credential before database work and replacement writes succeeded. Redis transactions now commit credential/index changes atomically after user validation; logout and account purge cannot be undone by a concurrent refresh.
- Revocation timestamps could reject a legitimate new sign-in within the same second. JWT issue timestamps now retain the precision used by revocation cutoffs.
- Matching an email could overwrite a different existing Google/Apple subject. Provider identity conflicts are rejected. Session-store outages during sign-in return the existing retryable 503 response.
- Attachment URLs could receive a bearer token merely because their path contained `/attachments/`. Only attachment paths under the configured Recall API origin and base path receive credentials.
- The HTTP streaming boundary disconnected Stop after response headers. The stream's cancellation signal now remains attached through its body.
- Failed or obsolete notification startup reads could reject without a handler or navigate after the listener's session ended. Those outcomes are handled without restoring stale navigation.

## Verification

- Backend: 3,298 local tests passed with 85.54% coverage; full Ruff, formatting and mypy checks passed. The unchanged coverage gate is 80%.
- The 26 PostgreSQL integration tests run against CI's isolated database. The local sandbox prevents PostgreSQL shared-memory initialization, so the configured development database was not migrated for validation.
- Mobile: all 2,158 tests across 262 suites passed, including credential/transport, provider, bootstrap, cache, onboarding and notification regressions. TypeScript passed; full lint reported no errors and 180 warnings; changed auth files have no warnings.
- Web: TypeScript and lint passed. CI results, including isolated PostgreSQL validation, are recorded on the associated PR.
- Independent reviews found no actionable backend or mobile credential/transport regressions.

The existing strict refresh replay policy is preserved: if rotation commits but its successful response is lost, another sign-in can be required. This review does not introduce a token-reuse grace period.

## Native verification blocker

The installed iPhone simulator app is linker-signed, reports no team identifier and contains no signing entitlements. The environment exposes no valid code-signing identities. The same native build reports notification keychain errors, and its missing entitlements explain why secure credential writes fail. These findings are consistent with the existing project note in `.cursor/rules/lessons.mdc` and [Apple's keychain entitlement guidance](https://developer.apple.com/documentation/security/errsecmissingentitlement).

The updated app was opened in that simulator: secure-storage startup failure displays the recoverable error screen and Retry control. Retrying returns to that screen while the native signing problem persists. Successful credential persistence remains unverified in this build.

Finish native verification by configuring the app's Apple development signing identity/team in Xcode and rebuilding with `pnpm expo run:ios` from `apps/mobile`, following [Expo's signing setup](https://github.com/expo/fyi/blob/main/setup-xcode-signing.md). Do not disable code signing or replace secure credential storage with plain files. The required device check is sign-in → JavaScript reload/relaunch → session refresh → sign-out → relaunch, followed by native Google/Apple callback testing.

Until that native check is complete, this feature is code-validated but not fully verified in a correctly signed device build. Nothing in this change deploys the app or certifies unrelated features.
