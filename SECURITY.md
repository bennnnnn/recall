# Security Policy

Report vulnerabilities privately. Do not open a public GitHub issue for secrets, auth bugs, or anything that could be exploited.

## Report

Use [GitHub private vulnerability reporting](https://github.com/bennnnnn/recall/security/advisories/new) on this repository.

Include the affected surface (API route, mobile screen, job), how to reproduce, and impact. Do not attach production secrets.

We will acknowledge the report and say whether we are fixing it, need more detail, or do not consider it a vulnerability.

## What this app actually does

- **Backend holds provider keys.** OpenRouter, Google, RevenueCat, R2, Tavily, Mathpix, and similar live only in `apps/api/.env` (Fly secrets in production). The Expo app never embeds those keys.
- **Tokens on device** go in `expo-secure-store`, not AsyncStorage. Access JWTs last 60 minutes; refresh tokens last 30 days in Redis (`jwt_expire_minutes`, `jwt_refresh_expire_days`).
- **Production boot** refuses `DEV_AUTH_ENABLED` and `MOCK_LLM_ENABLED`. CORS must be an explicit origin list, not `*`.
- **LLM structured output** is validated with Pydantic before it is written. Untrusted attachment and OCR text is wrapped before it reaches the model.
- **No arbitrary code execution.** Chat code is rendered only. HTML/CSS/JS may run inside the sandboxed preview WebView (dev/production build, not Expo Go). Python and shell are never executed.
- **Symbolic math** is server-side SymPy in isolated workers. The phone only renders.

## Out of scope for this file

App Store / Play Store signing, RevenueCat dashboard access, and Fly/Neon/Upstash IAM are operator secrets. Rotate them in those consoles; do not commit them.
