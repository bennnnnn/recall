# Security Policy

Report vulnerabilities privately. Do not open a public GitHub issue for secrets, auth bugs, or anything that could be exploited.

## Report

Use [GitHub private vulnerability reporting](https://github.com/bennnnnn/recall/security/advisories/new) on this repository.

Include the affected surface (API route, mobile screen, job), how to reproduce, and impact. Do not attach production secrets.

We will acknowledge the report and say whether we are fixing it, need more detail, or do not consider it a vulnerability.

## What this app actually does

- **Backend holds provider keys.** OpenRouter, Google, RevenueCat, R2, Tavily, Mathpix, and similar live only in `apps/api/.env` (Fly secrets in production). The Expo app never embeds those keys.
- **Tokens on device** go in `expo-secure-store`, not AsyncStorage. Access JWTs last 60 minutes; refresh tokens last 30 days in Redis (`jwt_expire_minutes`, `jwt_refresh_expire_days`). Sign out, sign out everywhere, removing one device, refresh-token reuse and account delete all revoke live access tokens too (`core/access_tokens.py`).
- **Sign in with Apple** requires a nonce: the app gives Apple SHA-256 of a random value and sends the raw value; the server accepts the identity token only when they match. Deleting an Apple-linked account on iOS runs Sign in with Apple once more; the server trades that fresh code for the user's Apple token and revokes it (a client-secret JWT signed with `APPLE_PRIVATE_KEY`, `gateways/apple_revoke.py`). Nothing Apple issues is stored. Best effort: Apple being down, or the key unset, never blocks the delete; closing the Apple sheet cancels it.
- **One account per email, joined only by the address's owner.** A Google or Apple sign-in whose id matches no account joins the account holding the same email only when that provider owns the address: Google for Gmail and for a Workspace address whose token's `hd` is its domain, Apple for its relay addresses and iCloud/me.com/mac.com. Otherwise sign-in answers 409 and the app says to sign in the way the account did before (`modules/account/email_authority.py`). A provider's "verified" flag alone is not proof the person controls the address.
- **Per-user data**: every route that takes an id answers another account with 404 (`app/tests/security/`). Account delete removes rows, stored files, the user's Redis keys and the user's entries in the background-jobs stream and its dead-letter queue (their payloads carry chat text); export covers everything stored about the user. A registered push token moves to another account only from the same app install (its device id); a token row saved before device ids existed stays with its owner (`repositories/push_tokens.py`).
- **Limits survive deleting the account.** So that deleting an account and signing in again cannot reset today's limits, account delete keeps one Redis key, `quota_carry:<HMAC-SHA256 of "google:<sub>" or "apple:<sub>", keyed with the server's JWT secret>`. It holds only counts: today's tokens, uploads, voice, web searches, image generations and photo lookups, and this month's live talk seconds. It never holds the raw Google/Apple id, the user id or any content. When that same sign-in creates a new account, the new account's counters are raised to those counts and the key is deleted. Otherwise it expires when the UTC month ends, after at most 35 days (`modules/account/quota_carryover.py`).
- **Error reports** (Sentry) carry no request bodies and no stack-frame variables, so prompts and tokens stay out of them.
- **Production boot** refuses `DEV_AUTH_ENABLED` and `MOCK_LLM_ENABLED`. CORS must be an explicit origin list, not `*`.
- **LLM structured output** is validated with Pydantic before it is written. Untrusted attachment and OCR text is wrapped before it reaches the model. The model's `generate_image` tool is offered only when the user's own message asks for a picture, and a tool the turn was not offered never runs, so text in a web result or a file cannot spend the user's image allowance (`modules/chat/tool_loop/`).
- **No arbitrary code execution.** Chat code is rendered only. HTML/CSS/JS may run inside the sandboxed preview WebView (dev/production build, not Expo Go). Python and shell are never executed. The preview holds no app token, and page script cannot navigate it away or open other URLs and apps (`allowHtmlRunNavigation` in `apps/mobile/lib/webView.ts`).
- **Symbolic math** is server-side SymPy in isolated workers. The phone only renders.

## Out of scope for this file

App Store / Play Store signing, RevenueCat dashboard access, and Fly/Neon/Upstash IAM are operator secrets. Rotate them in those consoles; do not commit them.
