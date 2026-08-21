# Production rollback

Use this runbook when a release passes deployment but causes production errors.
Rollback is an incident action, not a substitute for the pre-launch gate.

## Before every deploy

1. Run `./scripts/dev.sh check`.
2. Confirm `cd apps/api && uv run alembic current` matches `uv run alembic heads`.
3. Record the current Git SHA, Fly image reference, mobile build numbers, and any
   secret or `fly.toml` changes in the release notes.
4. Keep the previous production environment file in secure storage. Never commit it.

## API rollback

Fly rollback means redeploying a known-good image; it does not revert secrets,
configuration, or database data.

```bash
fly releases --app recall-api --image
fly deploy --app recall-api --image <known-good-image-reference>
```

After redeploy:

```bash
API_URL=https://<api-host> ./scripts/verify-production.sh --live
fly status --app recall-api
fly logs --app recall-api
```

Confirm both `app` and `worker` processes are healthy. If configuration changed,
restore the prior reviewed `fly.toml` and secrets separately, then deploy the known-good
image again.

## Database migration failure

The Fly release command runs `alembic upgrade head` before new machines start. If it
fails, the application image should not replace the healthy release.

- Do not run an automatic downgrade against production data.
- Inspect the failed migration and database state.
- Prefer a forward fix that is compatible with the currently running application.
- Test the repair against a Neon branch or restored snapshot before production.
- Run `uv run alembic current` and `uv run alembic heads` after recovery.

If a migration completed but the new application is unhealthy, verify the prior image
is schema-compatible before redeploying it. Otherwise ship a forward-compatible fix.

## Worker and job recovery

Confirm the worker is present and healthy:

```bash
fly scale count app=1 worker=1 --app recall-api
fly ssh console --app recall-api -C 'curl -sf http://127.0.0.1:8001/health/ready'
```

Inspect the dead-letter queue before replaying:

```bash
cd apps/api
uv run python ../../scripts/replay_dlq.py --list
```

Replay only after the failing handler or dependency is fixed. Do not repeatedly replay
poison jobs into the same failure.

## Mobile release recovery

There is no production over-the-air update path. A bad native release must be replaced
through App Store Connect and Play Console.

1. Stop the staged rollout or pause the release.
2. Keep the prior approved version available where the store allows it.
3. Build the fix from a reviewed commit with the production EAS profile.
4. Re-run the physical-device sections in `docs/QA_MATRIX.md`.
5. Submit an expedited review only when user impact justifies it.

Never rotate `JWT_SECRET` as a rollback shortcut; rotation signs every user out. Never
force a database downgrade solely to match a mobile version.
