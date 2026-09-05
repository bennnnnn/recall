# Learning: structured lessons and reliable progress

## Product behavior

Learning remains English and Spanish vocabulary, reached through the drawer's
Learning entry. Recall manages lesson content. Users can create a class, set a
daily goal, study, and export; manual content/class edit and delete controls
are removed. Account export and account erasure remain available.

The lesson map identifies the next group, shows today's saved completions, and
keeps later groups visible with their access state. Teaching cards show the
full definition, vocabulary classification, pronunciation action, and at least
two examples. Questions follow teaching, with explicit correct/try-again
feedback and a learned/reviewed completion summary. Naturally inflected
examples remain intact instead of becoming ungrammatical cloze questions.

The active catalog contains 387 English entries across 20 groups and 519
Spanish entries across 43 groups. Original groups and word UUIDs retain their
order and identity; new expression, phrasal-verb, idiom, and proverb groups
append to the path. Every active entry has at least two distinct examples in
the target language. Existing verified IPA remains; new multiword groups use
the pronunciation action without invented transcriptions.

Optional sound cues are original, bundled 0.32-second WAVs. Spoken feedback and
lesson pronunciation use device speech. Controls belong to the user and audio
is canceled when the lesson leaves focus, the app backgrounds, or the account
changes. Cues do not change the global recording/audio category. They inherit
the active device audio mode; this change does not introduce a global audio
session manager.

## Correctness boundaries

- A question outcome has an owner-scoped attempt UUID. Identical retries return
  the current item and the original outcome without writing another event.
  Reusing the UUID for a different outcome conflicts. The client retains the
  failed answer and UUID until its save succeeds.
- Question attempts and correct answers are separate from word completion.
  Only a final correct check advances mastery and SM-2. A wrong review records
  activity without demoting an already-mastered word or rewinding its schedule.
  First mastery is retained; learned/reviewed classification comes from the
  immutable server outcome, including retries and overlapping visits.
- Stats and history distinguish completed, attempted, and missed words. A
  partial attempt counts as study activity. Review-only days retain their word
  details, and first mastery is not erased by a later partial review.
- Ordinary chat questions can distinguish no class, an unstarted class, and
  actual saved progress. Context includes recent study, due reviews, and daily
  history without injecting the full vocabulary catalog.
- Opt-in reminders use actual activity and include mastered words due for
  review. Existing timezone, daily deduplication, and notification preferences
  remain in force. Learning progress chrome is not added to Home.
- Content reconciliation updates only catalog-owned content. It preserves
  item IDs, notes, ownership, mastery, schedules, and history. Null-ID older
  rows are adopted only with a known source fingerprint; unknown custom rows
  are preserved. SQL compares the fingerprint again before adoption.
- Account exports include classification, last completion, and owner-scoped
  practice events, paged by immutable timestamp/ID with an explicit 20,000-event
  limit. Database sessions close before streaming chunks. Event foreign keys
  cascade with account, project, or item erasure.

## Validation and release

Regression coverage includes request retries, account/visit changes, concurrent
practice, content refresh preserving progress, history day boundaries, missed
review details, notification eligibility, export ownership/paging, settings
rollback, and stale PDF sharing. Catalog tests verify all original active UUIDs
and all older catalog references remain resolvable.

Local API validation uses mocked providers and isolated local SQL. PostgreSQL
locking, migration, and cascade cases run in CI's disposable PostgreSQL service;
they are not run against a developer or production database. The coverage gate
remains 80%. Mobile validation includes the complete Jest suite, TypeScript,
ESLint, and production exports for iOS, Android, and web.

Final local gates: 3,521 API tests passed with 86.27% coverage; all 91
PostgreSQL cases collected for CI. Mypy checked 636 files; Ruff lint/format
passed. Mobile passed 2,602 tests across 299 suites and TypeScript. ESLint
reported zero errors and 142 existing warnings; changed files have no warnings.
Production exports passed for all three platforms.

Visual checks render the actual React Native components through React Native
Web with fixture data, native audio disabled, and reduced motion. They cover
English teaching, Spanish idioms, long proverbs, correct/incorrect answers,
completion, and the lesson map in light/dark themes at 393×852 and 320×568.
This caught and fixed short glosses replacing full definitions and oversized
proverb question text. The preview is not a native-device or live-provider test.

Apply migration `0079_learning_practice` before releasing clients using the new
practice endpoint. Existing catalog rows refresh through the language-path
job; the migration does not delete existing progress. Physical-device speech,
silent-switch behavior, background/recording transitions, and opt-in push/email
delivery remain release smoke checks. No deployment is performed by this review.
