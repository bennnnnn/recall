Vendored `deepmerge` for `@expo/config` and `jest-config` (both `deepmerge ^4.3.1`).

Upstream has no release past 4.3.1 that fixes GHSA-gcqx-w48m-w2h4: `mergeObject()` wrote
each key by assignment, so a source key `__proto__` replaced the returned object's prototype
whenever the target had no `__proto__` of its own to block it (a null-prototype object). This
copy is 4.3.1's CommonJS build with every key written as an own data property
(`Object.defineProperty`), and reports version 4.3.2 so Dependabot's `<= 4.3.1` range clears.
`lib/__tests__/deepmergeVendor.test.ts` holds the fix and the merge behaviour the two callers use.

Remove when upstream publishes a patched release and both callers adopt it.
