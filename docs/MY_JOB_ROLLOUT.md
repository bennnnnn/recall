# Premium My Job rollout

My Job saves one versioned profile shared by chat and the mobile screens. Searches
return a durable run ID immediately. A worker owns retrieval, posting verification,
publication, and a separate notification outbox; disconnecting chat or closing the
app does not abandon the search.

## Enablement

1. Apply Alembic migrations through `0103_remove_job_resume` before deploying the
   API and worker together. Migration 0102 converts Interviewing, Offer, and
   Rejected to Applied and removes those allowed statuses. Jobs, bookmarks and
   notes are retained. Migration 0103 removes My Job résumé columns and increments
   revisions for profiles with résumé data, preventing stale assessments from publishing.
   Uploaded attachments remain available to their owning chats. Migrations 0100/0101 backfill
   unambiguous legacy locations; uncertain geography and salary currency require
   review.
2. Keep `JOB_SEARCH_PREMIUM_ENABLED=false` during migration and smoke checks. Set it
   to `true` for the controlled release. `WEB_SEARCH_ENABLED`, Tavily credentials,
   the durable Redis worker, and the periodic My Job scheduler must also be enabled.
3. Keep `JOB_SEARCH_ZAI_COMPARISON_ENABLED=false`. Live runs always use Tavily Basic,
   Tavily page extraction and the grounded ranker. Verify current provider prices
   before changing `JOB_SEARCH_TAVILY_CREDIT_USD`.
4. Test a Pro account, a free account, and an expired subscription. Reads and search
   deletion remain available after expiry. Expiry pauses the search; renewal alone
   does not resume it. Resume is an explicit user action.
5. Test notification permission, a valid device token and a failed send. Notification
   taps include the run ID so the app loads that search's result set.

A new profile defaults to ten results on weekdays at 8 AM in the account timezone.
Experience and work arrangements stay broad until the user narrows them. A salary
minimum is optional and numeric-only in the form. The form keeps an established
currency or displays the selected country’s currency as its pay unit. Editing
preferences saves them and keeps
paused searches paused. Only an explicitly requested search starts another run.

## Reliability contracts

- Profile revisions prevent a stale run from publishing against edited preferences.
  Saved jobs and application history stay readable; older comparisons are marked
  outdated. Legacy full-profile saves preserve richer fields they omit.
- Five manual logical runs are allowed per user-local day, with a ten-minute
  cooldown. Scheduled runs do not use the manual allowance. Idempotency keys and
  active-run coalescing share the run and allowance. Deleting/recreating the profile
  does not reset the user's daily allowance.
- Each run reserves at most six retrieval queries and thirty posting fetches.
  Checkpoints resume completed phases after worker restarts. A crash before a
  checkpoint can consume reserved budget without producing results; retries cannot
  exceed those limits. Search-provider daily limits and the global spend guard also
  apply to workers, posting analysis and cover-letter assistance.
- Unreadable pages, closed postings and confirmed mismatches are rejected. Extracted
  facts require supporting text from a specific posting. Unknown requirements,
  overlapping pay ranges and incomparable currencies/periods remain in the single
  Matches list with the unresolved facts on each job. There is no separate Possible
  matches view. Currency conversion and assumed working hours are never used.
- Country-wide coverage is a bounded sample of selected sources, never an exhaustive
  claim. Partial provider/query/extraction failures are recorded separately from a
  successful search with no results.
- Cross-site duplicates merge only by canonical posting URL or explicit employer and
  requisition identity. A shared title and employer do not establish a duplicate.
- Results and a notification event commit together. Only genuinely new qualifying
  matches generate an event. Accepted per-device tickets are persisted and skipped
  on retries; receipt processing prunes invalid tokens. There is an unavoidable
  crash window between provider acceptance and saving that acceptance, so delivery
  is not an exactly-once guarantee.

## Monitoring

Use `job_search_runs` for queued/running/completed/failed/limited/cancelled outcomes,
creation/start/finish times, partial coverage, qualifying/possible/new counts,
provider usage and reserved/estimated costs. Structured `my_job_run_finished` logs
include outcome, latency, counts and usage. `my_job_assistance_usage` records model
usage for cover-letter assistance. No posting contents or candidate background
are included in these metrics.

Track failures, successful empty results, partial-result rate, p50/p95 latency,
reserved search/extraction cost, model-token cost and cost per new qualifying job.
Track `job_notification_events` pending age, attempts, delivered/suppressed states,
accepted device tickets and receipt failures. Alert on old queued runs, expired
leases, persistent outbox backlog and a material increase in failure or empty rates.

## Provider comparison

`SearchProvider`, `PageExtractor` and `PostingRanker` are separate interfaces. The
optional `ZaiComparisonSearch` adapter requires the comparison flag and its own key;
it is never selected by a production worker. Run an explicitly authorized benchmark
with identical role/location profiles and the same posting-verification rules.
Include multiple professions/countries, remote exclusions, salary currencies and
periods, undisclosed pay, expired postings and distinct requisitions.

Count all search requests, extraction credits, input/output tokens and duplicate
results. Compare total cost per verified qualifying opening, factual correctness,
filtering accuracy, yield and latency. A lower token price or search price alone is
insufficient. Keep Tavily until the alternative is cheaper at equal or better
verified-job accuracy. Official references: [Z.ai GLM capabilities](https://docs.z.ai/guides/llm/glm-5.3),
[Z.ai pricing](https://docs.z.ai/guides/overview/pricing),
[Tavily credits](https://docs.tavily.com/documentation/api-credits).

## Rollback and client QA

Disable `JOB_SEARCH_PREMIUM_ENABLED` to stop new search admission and external worker
search spending. Retain the additive schema and readable history. The notification
outbox is independent; disable `PUSH_ENABLED` when notification delivery must also
stop. Avoid downgrading these migrations after real runs have been saved.

Before release, check the complete setup, job list, detail, chat and notification
flows on native iOS/Android at small sizes and large accessibility text, in both
light and dark themes. Check screen-reader labels and minimum touch targets. Local
component previews supplement native QA; they do not substitute for testing platform
permissions, backgrounding and real notification receipts.
