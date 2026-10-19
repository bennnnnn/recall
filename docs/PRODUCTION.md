# Recall — Production Provisioning Checklist

Step-by-step guide to provision production infrastructure. Pair with [`README.md`](../README.md) §Production deployment and run [`scripts/verify-production.sh`](../scripts/verify-production.sh) after each stage.

---

## 1. Database (Neon Postgres + pgvector)

- [ ] Create Neon project (or Fly Postgres with pgvector)
- [ ] Enable `vector` extension: `CREATE EXTENSION IF NOT EXISTS vector;`
- [ ] Set `DATABASE_URL` as `postgresql+asyncpg://...?sslmode=require`
- [ ] Run migrations: `cd apps/api && uv run alembic upgrade head`
- [ ] Confirm `uv run alembic current` matches `uv run alembic heads`

```bash
cd apps/api
uv run alembic heads
uv run alembic current
# The same single revision should be shown by both commands.
```

---

## 2. Redis (Upstash)

- [ ] Create Upstash Redis database
- [ ] Set `REDIS_URL=rediss://...` (TLS URL)
- [ ] Verify connectivity from Fly region (latency to Upstash region)

---

## 3. Object storage (Cloudflare R2)

Required for production attachments (`STORAGE_BACKEND=r2`).

- [ ] Create R2 bucket (e.g. `recall-attachments`)
- [ ] Create API token with R2 read/write on bucket
- [ ] Set secrets:
  - `STORAGE_BACKEND=r2`
  - `R2_ACCOUNT_ID`
  - `R2_ACCESS_KEY_ID`
  - `R2_SECRET_ACCESS_KEY`
  - `R2_BUCKET`
- [ ] Smoke-test: upload image in app → confirm object in R2 → download in chat
- [ ] Bucket lifecycle: abort incomplete multipart after 7 days. Account delete
  purges known keys then enqueues a `storage_sweep` job that `list`+`delete`s
  leftover objects under `{user_id}/` (covers Redis reaper never running). Do
  not weaken `reap_orphan_attachments`. Unconfirmed original uploads are reaped
  after `attachment_pending_orphan_hours` (default 1h). Hidden clones stay until
  `attachment_orphan_grace_hours` (default 24h) — that billed window is
  intentional. Optionally add an R2 lifecycle rule
  that expires unprefixed leftovers as a last resort.

Native iOS/Android uploads are not subject to browser CORS. Before enabling the
planned web client, add an R2 bucket CORS policy that allows `PUT`/`GET` from the
exact production web origin and only the headers used by presigned uploads.

---

## 4. Fly.io API

- [ ] `fly launch` (or connect existing app to repo root; uses `apps/api/Dockerfile`)
- [ ] Scale processes: `fly scale count app=1 worker=1` (worker is not
      covered by `min_machines_running`; pin it or jobs stop silently)
- [ ] Confirm worker health: `fly ssh console -C 'curl -sf http://127.0.0.1:8001/health/ready'`
  (or check worker logs show the jobs consumer started)
- [ ] Set **all** secrets (enforced by `validate_production_settings`):

| Secret | Required | Notes |
|--------|----------|-------|
| `ENVIRONMENT` | yes | `production` |
| `DEV_AUTH_ENABLED` | yes | `false` |
| `MOCK_LLM_ENABLED` | yes | `false` |
| `JWT_SECRET` | yes | ≥32 random chars |
| `DATABASE_URL` | yes | asyncpg URL |
| `REDIS_URL` | yes | `rediss://` |
| `GOOGLE_CLIENT_ID` | yes | Google Sign-In (ID-token audience) |
| `OPENROUTER_API_KEY` | yes | Chat + composer STT (`gpt-transcribe`) |
| `OPENAI_API_KEY` | Live Talk only | WebRTC Realtime; OpenRouter has no Realtime API |
| `CORS_ORIGINS` | yes | Explicit origins, never `*` |
| `REVENUECAT_WEBHOOK_AUTH` | yes | Shared secret for the webhook |
| `REVENUECAT_SECRET_KEY` | yes | REST API; every access change, TRANSFER, plan sync, hourly reconcile |
| `REVENUECAT_ENTITLEMENT_ID` | no (default `pro`) | Top plan's entitlement; keep `pro` so earlier subscribers stay on Pro |
| `REVENUECAT_PLUS_ENTITLEMENT_ID` | no (default `plus`) | Lower paid plan's entitlement |
| `TAVILY_API_KEY` | if web search | |
| `TRUST_X_FORWARDED_FOR` | yes (set in `fly.toml` `[env]`) | `true` behind Fly. Unset, every per-IP rate limit keys on Fly's proxy address and becomes one global bucket; production boot logs a warning. |
| `DAILY_GLOBAL_SPEND_USD` | yes | UTC-day provider $ cap (every model call, images, voice, live talk); must be > 0. At the cap new chat turns are refused: see [Load and abuse limits](#load-and-abuse-limits) |
| R2 vars | yes | See §3 |

```bash
# Deploy
fly deploy

# Verify
curl -s https://<your-api>/health/ready
```

- [ ] Health monitor: `GET /health` (liveness) and `GET /health/ready` (Postgres;
      Redis may report `degraded` without 503)
- [ ] RevenueCat webhook → `https://<api>/webhooks/revenuecat` with `Authorization` header
- [ ] Plans and store products set up per [§4b](#4b-plans-and-revenuecat-free-plus-pro)

---

## 4b. Plans and RevenueCat (Free, Plus, Pro)

Three plans. "Plus" and "Pro" are working names: the app shows them from i18n
(`plans.plus`, `plans.pro` in all nine locale files), so renaming them is a
copy change. The server only knows the ids `free`, `plus`, `pro`.

| | Free | Plus (lower paid) | Pro (top) |
|---|---|---|---|
| Models | free pool | all | all |
| Tokens / day | 100k | 500k | 500k |
| Voice input / day | — | 200 | 200 |
| Natural read-aloud / day | — (phone voice only) | 100 | 100 |
| AI images / day | 3 | 10 | 15 |
| Live talk | — | — | 60 min / UTC calendar month |

Every number is a `core/config.py` setting (`<NAME>`, `<NAME>_PLUS`,
`<NAME>_PRO`; see `apps/api/.env.example`). A metered feature belongs to a plan
when its number is above zero, so moving a feature between plans is a secret
change, not a release. `modules/billing/entitlements.py` is the one place that
decides; the server refuses (403) anything a plan lacks, whatever the app shows.

**Prices are never in code.** Set them in App Store Connect and Play Console;
the app shows the store's localized price from the RevenueCat offering.

### What to create (owner)

1. **App Store Connect** — one subscription group (e.g. "Recall") holding two
   auto-renewable monthly subscriptions, e.g. `recall_plus_monthly` ($7.99) and
   `recall_pro_monthly` ($13.99). Rank Pro **above** Plus in the group (level 1),
   so Plus → Pro is an immediate upgrade and Pro → Plus takes effect at renewal.
   If a Pro product already exists, keep it as the Pro product in that group.
2. **Play Console** — two subscriptions (e.g. `recall_plus`, `recall_pro`), each
   with a monthly base plan. The app replaces the Plus subscription when someone
   buys Pro (prorated, immediate), so nobody pays for both.
3. **RevenueCat → Entitlements** — keep `pro` (the single-plan id; existing
   subscribers stay on Pro with nothing lost) and add `plus`. Attach the Plus
   products to `plus` and the Pro products to `pro` (attaching Pro to both is
   fine; the server takes the higher plan).
4. **RevenueCat → Offerings** — the current offering holds two packages with the
   custom identifiers **`plus_monthly`** and **`pro_monthly`**. (An offering with
   only the old monthly package is shown as Pro, so the switch can be staged.)
5. **RevenueCat → Project settings** — keep restore behavior **Transfer to new
   App User ID** (the default). Two accounts on one Apple ID: the account that
   restores gets the plan and the other drops to Free on the TRANSFER webhook.
6. **Webhook** — unchanged URL and auth. The server re-reads the subscriber on
   every event that can change access; BILLING_ISSUE (grace period),
   SUBSCRIPTION_PAUSED and auto-renew-off CANCELLATION keep access until
   EXPIRATION. The worker re-checks every paid row hourly
   (`BILLING_RECONCILE_INTERVAL_SECONDS`).
7. **Deploy order** — migrate (`0107_plus_plan` only widens `ck_users_plan`;
   no rows change), deploy the API, then ship the app build with the new
   offering. An older app build still sees Pro correctly; it does not offer Plus.

### Live talk minutes

The phone talks to OpenAI over WebRTC after the server mints a session, so the
server meters at its own edges: a mint reserves `min(minutes left,
LIVE_TALK_MAX_SESSION_SECONDS)` (refused under `LIVE_TALK_MIN_SESSION_SECONDS`),
the session may save turns and use voice tools only for that reservation, the
phone hangs up when it ends, and `POST /speech/live/end` settles it to the time
the server measured (never refunding more than was reserved). A phone that
never reports keeps the whole reservation charged. The global spend counter
follows the same reservation: a mint adds the reserved minutes at
`LIVE_TALK_SPEND_USD_PER_MINUTE` ($0.20, `services/quota/spend.py`) and the
end report gives back the unused part, so saved turns add no spend. A session
may save one turn per 5 reserved seconds (at least 12) and a user 20 turns a
minute; past either, `POST /speech/live/persist` answers 429. Known limit: the
server cannot hang up the OpenAI call itself, so a modified client could keep
talking past its reservation (nothing is saved, no tools); that time is not
on the spend counter.

### QA (sandbox / test track)

- [ ] Free: mic and live talk open the plans; read-aloud uses the phone voice;
      3 AI images, then the limit message
- [ ] Buy Plus: voice input and read-aloud work, live talk opens the plans,
      Settings shows Plus and "Upgrade to Pro"
- [ ] Plus → Pro: one subscription in the store afterwards; live talk works and
      Settings shows minutes left; a 2-minute call takes about 2 minutes
- [ ] Pro → Plus (store downgrade): Pro until renewal, then Plus
- [ ] Cancel, let it expire: back to Free on the next request
- [ ] Refund (support): back to Free; restore on a second device; sign in as a
      second account on the same Apple ID and restore (TRANSFER)

---

## 5. Mobile (EAS)

- [ ] Configure EAS project ID in `apps/mobile/.env` / EAS secrets
- [ ] Set `EXPO_PUBLIC_API_URL=https://<api-host>`
- [ ] Set Google client IDs (iOS + web) in EAS secrets
- [ ] Set RevenueCat API keys per platform
- [ ] Register the EAS **production** Android signing certificate SHA-1 with the
      Android OAuth client in Google Cloud (the debug SHA-1 is not sufficient)
- [ ] Release builds pass the config guard for API URL, EAS project ID, Google
      client IDs, and the platform's RevenueCat SDK key
- [ ] Build:
  ```bash
  cd apps/mobile
  eas build --platform ios --profile production
  eas build --platform android --profile production
  ```
- [ ] Submit to App Store / Play Console
- [ ] On-device QA per [`docs/QA_MATRIX.md`](QA_MATRIX.md)

### Over-the-air updates (EAS Update)

JavaScript and asset changes reach installed apps without a store release.
Builds made with the `production` profile listen on the `production` channel
(`preview` builds on `preview`). The app checks on launch, downloads in the
background, and runs the new code from the next launch.

- [ ] In EAS environment variables, keep every `EXPO_PUBLIC_*` value as
      **Plain text** or **Sensitive** (not **Secret**) in the `production` and
      `preview` environments, so `eas update` can bundle them
- [ ] Publish: GitHub **Actions → Publish app update** (channel + message), or
  ```bash
  cd apps/mobile
  RECALL_UPDATE_PROFILE=production eas update --channel production \
    --environment production --message "what changed"
  ```
- [ ] A build takes only updates for its own runtime version, which is the
      `version` in `apps/mobile/app.json`. **Bump that version and ship a store
      build** for any native change: a new native module, an Expo SDK upgrade, or
      a config plugin or permission change. An update sent to an older binary
      without that native code would crash it.
- [ ] Builds made before `expo-updates` was added cannot receive updates; install
      a new build once
- [ ] Review [`docs/ROLLBACK.md`](ROLLBACK.md) before the first store submission

---

## 6. Google Sign-In

- [ ] OAuth consent screen published (sign-in scopes only: openid, email, profile)
- [ ] Client IDs match the mobile bundle IDs and `GOOGLE_CLIENT_ID`
- [ ] Old deployments: unset `GOOGLE_CLIENT_SECRET` and `OAUTH_TOKEN_ENCRYPTION_KEY`
      (`fly secrets unset ...`); Calendar/Gmail were removed in migration `0106`

---

## 7. Landing & support

- [ ] Landing page live
- [ ] Support URL for store listings
- [ ] Privacy policy + terms URLs (served from API `/legal/*` or static site)

---

## 8. Observability (optional)

- [ ] `SENTRY_DSN` on API and mobile EAS secrets
- [ ] Fly metrics / external uptime on `/health/ready`
- [ ] Resend (`RESEND_API_KEY`) if transactional email enabled

---

## Verification commands

```bash
# Static checks (migration file, env template)
./scripts/qa-smoke.sh

# Against running local or deployed API
API_URL=https://your-api.fly.dev ./scripts/qa-smoke.sh --live

# Full provisioning report
./scripts/verify-production.sh
API_URL=https://your-api.fly.dev ./scripts/verify-production.sh --live
```

---

## Load and abuse limits

Defaults are sized for one shared-CPU `app` machine. Override with Fly secrets
or `[env]` only when you have a measured reason.

**Memory:** the API warms `SYMPY_MAX_WORKERS` (3) SymPy workers at boot, each
its own process. Measured PSS: the API about 270 MB at boot and 400 MB under
load; each worker 90–150 MB (150 once a chemistry fence loads RDKit). That is
550–850 MB, more than a 512 MB machine without swap, so `fly.toml` gives the
`app` machine 1 GB. On 512 MB, run `SYMPY_MAX_WORKERS=1` and accept that a
second maths turn inside the 2 s slot wait gets an unverified answer.

| Setting | Default | What it protects |
|---------|---------|------------------|
| `MAX_REQUEST_BODY_BYTES` | `1048576` (1 MiB) | Every HTTP body. A declared `Content-Length` over the cap gets 413 before a byte is read; a chunked body is cut off one chunk past it. `0` disables. |
| `MAX_UPLOAD_REQUEST_BODY_BYTES` | `12582912` (12 MiB) | Photo/audio routes only: `/speech/transcribe`, `/{math,physics,chemistry}/scan/read`, `/attachments/{id}/upload`. Each route still checks its exact limit. |
| `ATTACHMENT_OCR_MAX_PAGE_PIXELS` | `4000000` | Pixel budget per rendered PDF page (scanned-PDF OCR, chat path and index job). The page size comes from the file: a 435-byte PDF with one 14400x14400 pt page peaked at 5.1 GB RSS before; now 259 MB. A letter page at the default 1.5x scale (~1.1 MP) is unaffected. |
| `ATTACHMENT_IMAGE_MAX_DECODE_PIXELS` | `16000000` | Largest decode for a gallery thumbnail (`GET /attachments/{id}/file?w=`), which now runs off the event loop. JPEG decodes at a reduced scale first, so phone photos work; a lossless image past the budget gets 422. A 505 KiB 13000x13000 PNG used to add ~650 MB RSS and block the loop 1.4s. `0` disables. |
| `JOBS_STREAM_MAX_LEN` | `50000` | Hard ceiling on the `recall:jobs` Redis Stream, applied on every `XADD`. The 10k soft trim only runs while nothing is pending, so a worker that died mid-job used to leave the stream unbounded. Past the ceiling the oldest jobs are dropped (they are best-effort). `0` disables. |
| uvicorn `--ws-max-size` (in `fly.toml` and `apps/api/Dockerfile`) | `1048576` (1 MiB) | Largest WebSocket frame (uvicorn default 16 MiB). A chat frame is at most ~130 KB. Change both files together. |
| WebSocket frame budget (`modules/chat/ws_api.py`) | 120 frames/min per socket | Every frame after auth counts, including pings, cancels and invalid JSON (only message/regenerate were limited). Over budget the server sends `{"code": "rate_limited"}` and closes with 1008; a reply in progress is still saved. |
| `R2_CONNECT_TIMEOUT_SECONDS` / `R2_READ_TIMEOUT_SECONDS` / `R2_MAX_ATTEMPTS` | `5` / `20` / `3` | boto3 calls to R2 (attachment reads on the chat path, deletes, sweeps). botocore's defaults were 60s + 60s with 5 attempts, each holding a default-executor thread (5 on one CPU). Retries use botocore's `standard` mode (jittered backoff). |
| `GOOGLE_AUTH_TIMEOUT_SECONDS` | `10` | Google cert fetch during sign-in (google-auth defaulted to 120s). A failed or slow fetch answers 503 + `Retry-After`, not 500 or 401. |
| `DB_CONNECT_TIMEOUT_SECONDS` / `DB_COMMAND_TIMEOUT_SECONDS` | `10` / `120` | asyncpg connect (default was 60s) and every statement (default was unbounded), including the `pool_pre_ping` on each checkout, so a half-open pooled connection can no longer hang a request. Client-side, so it works through Neon's pooler. Generous because account delete is one cascading `DELETE`. Migrations are not affected. A pool, connect or statement timeout, or a dropped connection, now answers `503` + `Retry-After: 5` instead of a bare 500. |
| `JOB_TIMEOUT_SECONDS` | `900` | Deadline for one attempt of one background job. An attempt that runs out goes to the DLQ without retry. An entry delivered more than 5 times without an ack (it keeps killing the worker) also goes to the DLQ on reclaim. |

Readiness answers inside Fly's 5s check timeout: `/health/ready` gives Postgres 3s
(then 503) and Redis 1s (then `"redis": "degraded"`, still 200); the worker's
probe gives Redis 3s. A stalled Redis used to time out readiness on every
machine at once.

### Spend and daily tokens

**`DAILY_GLOBAL_SPEND_USD`** is a kill-switch on estimated provider dollars per
UTC day (Redis `spend_musd:<date>`, `core/spend_counter.py`). What adds to it:

- a chat turn: catalog price x its tokens, at finalize (`modules/chat/post_turn.py`);
- every other model call, priced from its tokens by the gateway that makes it
  (`gateways/llm_spend.py`): memory extraction and consolidation, titles,
  suggestions, compression, follow-up questions, attachment OCR, embeddings,
  the web-search classifier, the reference resolver, maths extraction;
- a fixed price per call for images, photo lookup, scan reads, voice input and
  read-aloud (`services/quota/spend.py`);
- live talk by time: the reserved minutes at mint, settled at
  `POST /speech/live/end` ([§4b](#live-talk-minutes)).

Once the day's total reaches the cap, until 00:00 UTC:

- a new chat message or regenerate is refused before any model call. Both
  transports send `{"type": "error", "message": "Recall is at capacity for
  today, so new messages are paused for everyone. Try again after midnight
  UTC."}`. It has no `quota_exceeded` code, so the phone shows that text and
  not its upgrade prompt (the user's own allowance is not used up);
- image generation, photo lookup, voice, live talk and scan reads answer 429
  "… temporarily unavailable";
- background model jobs, the tool loop and follow-up questions are skipped.

A Redis error counts as over the cap (fail closed). Known gap: the tool rounds
of a turn that ends in a generated image are not charged (the image is).

**Daily tokens.** A turn reserves its estimate (the message plus
`MAX_OUTPUT_TOKENS`, x the model's quota multiplier) before it runs, or
whatever is left of the day when less is, and finalize settles to the actual
usage; a failed or cancelled turn gives the reservation back. Turns in
different chats share that one remaining budget, so opening many chats at once
cannot multiply the day's allowance. A turn that starts is not cut short to
fit: past the limit its extra tokens are forfeit (the counter is clipped), so
one turn is the most a user can go over. While a turn runs, the usage shown in
Settings includes its reservation.

**Scanned PDFs.** A PDF with no text layer is read with up to
`ATTACHMENT_OCR_INDEX_MAX_PAGES` vision calls by the index job, which first
takes one of the owner's daily image-upload slots (`DAILY_IMAGE_LIMIT*`). At
the cap the file stays attached but is not searchable that day; a PDF read
from its text layer gets the slot back.

---

## Cost telemetry dashboard queries

Each finalized chat turn logs `turn_cost … est_cost_usd=…` and accumulates
`usage_daily.est_cost_usd` from catalog prices × **raw** input/output tokens
(not quota-weighted). Apply migration `0061_usage_daily_est_cost_usd` before
relying on the column. It holds chat turns only: background model calls,
images, voice and live talk count on the Redis spend counter
([Spend and daily tokens](#spend-and-daily-tokens)), not here.

**Spend for one user in the current UTC month:**

```sql
SELECT
  user_id,
  SUM(est_cost_usd) AS est_cost_usd,
  SUM(input_tokens + output_tokens) AS weighted_tokens
FROM usage_daily
WHERE user_id = :user_id
  AND date >= date_trunc('month', timezone('UTC', now()))::date
GROUP BY user_id;
```

**Top spenders yesterday (UTC):**

```sql
SELECT user_id, est_cost_usd, input_tokens, output_tokens
FROM usage_daily
WHERE date = (timezone('UTC', now())::date - 1)
ORDER BY est_cost_usd DESC
LIMIT 50;
```

**Daily platform spend (last 14 days):**

```sql
SELECT date, SUM(est_cost_usd) AS est_cost_usd
FROM usage_daily
WHERE date >= (timezone('UTC', now())::date - 14)
GROUP BY date
ORDER BY date;
```

Note: `input_tokens` / `output_tokens` on `usage_daily` are **quota-weighted**;
`est_cost_usd` is independent of the quota multiplier. Compare log lines
(`turn_cost`) to catalog prices when validating the 3.5× R1 weight.

---

## Owner actions (you — not code)

These cannot be finished in a PR. Track them in the app under Lists → **Launch**
(created for the local Dev User), or follow [`docs/PRODUCTION.md`](./docs/PRODUCTION.md).

1. Install `flyctl` + `fly auth login`
2. Confirm Neon `DATABASE_URL` + `uv run alembic current` matches `uv run alembic heads`
3. Confirm Upstash `REDIS_URL` (`rediss://`) from the Fly region
4. Cloudflare R2 bucket + Fly secrets: `STORAGE_BACKEND=r2` + `R2_*`
5. Remaining Fly secrets (JWT, OpenRouter, Google, CORS, OAuth encryption key, RevenueCat,
   `ENVIRONMENT=production`, `DEV_AUTH_ENABLED=false`, `MOCK_LLM_ENABLED=false`)
6. `fly scale count app=1 worker=1` → `fly deploy` → `GET /health/ready`
7. EAS production builds (iOS + Android) with `EXPO_PUBLIC_API_URL=https://<api>`
8. On-device QA — [`docs/QA_MATRIX.md`](./docs/QA_MATRIX.md)
9. Google OAuth consent screen published (sign-in only)
10. Landing page + support URL + privacy/terms for store listings
11. Optional: `SENTRY_DSN` on API + mobile EAS secrets

---

## Launch blockers (from FEATURES.md)

1. Cost guards (speech, Tavily, R1 weight) — done in code
2. Provision Neon, Redis, R2, Fly, EAS
3. Landing page + support URL
4. On-device QA matrix (iOS + Android)
5. R2 production attachments end-to-end
