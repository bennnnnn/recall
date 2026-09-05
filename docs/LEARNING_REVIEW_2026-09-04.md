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

The map also opens a read-only Vocabulary overview. Learners can browse chapters,
search words and definitions, and read examples without starting a lesson or
changing progress. The class card labels mastered words as learned, so an
unstarted class does not misleadingly appear to contain zero words.

The active catalog contains only 40 English entries across four groups and 20
Spanish entries across two groups. English teaches conversation expressions,
phrasal verbs, idioms, and proverbs; Spanish teaches idioms and proverbs. Old
beginner vocabulary and groups are removed, including saved old/custom entries
and their practice history. Every retained entry has at least two distinct
examples in the target language. Multiword groups use the pronunciation action
without invented transcriptions.

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
  Correct lesson attempts do not erase later legacy/chat misses; mirrored wrong
  events count once per word/day and partial practice remains incomplete.
- Ordinary chat questions can distinguish no class, an unstarted class, and
  actual saved progress. Context includes recent study, due reviews, and daily
  history without injecting the full vocabulary catalog.
- Opt-in reminders use actual activity and include mastered words due for
  review. Existing timezone, daily deduplication, and notification preferences
  remain in force. Learning progress chrome is not added to Home.
- Catalog reconciliation removes inactive and null-ID words from supported
  Learning classes. Retained catalog IDs keep their item IDs, notes, ownership,
  mastery, schedules, and history. Class IDs and daily goals remain intact.
  Reads exclude retired content while a refresh is pending. Failed catalog jobs
  propagate to the retry/dead-letter workflow; deterministic refresh is independent
  of AI spending limits. Deduplication includes the catalog revision so old
  successes cannot hide updates.
- Account exports include classification, last completion, and owner-scoped
  practice events, paged by immutable timestamp/ID with an explicit 20,000-event
  limit. Database sessions close before streaming chunks. Event foreign keys
  cascade with account, project, or item erasure.

## Validation and release

Regression coverage includes request retries, account/visit changes, concurrent
practice, content refresh preserving progress, history day boundaries, missed
review details, notification eligibility, export ownership/paging, settings
rollback, and stale PDF sharing. Catalog tests verify the new active IDs and prevent retired words from returning.
PostgreSQL cases verify deletion cascades, retained progress, ownership, and
repeatable retirement migrations.

Local API validation uses mocked providers and isolated local SQL. PostgreSQL
locking, migration, and cascade cases run in CI's disposable PostgreSQL service;
they are not run against a developer or production database. The coverage gate
remains 80%. Mobile validation includes the complete Jest suite, TypeScript,
ESLint, and production exports for iOS, Android, and web.

Final validation results are recorded with the PR. The local harness explicitly
excludes live databases; PostgreSQL cases run in CI.

Visual checks render the actual React Native components through React Native
Web with fixture data, native audio disabled, and reduced motion. They cover
English teaching, Spanish idioms, long proverbs, correct/incorrect answers,
completion, the lesson map, and vocabulary browsing/search in light/dark themes at 393×852 and 320×568.
This caught and fixed short glosses replacing full definitions and oversized
proverb question text. The preview is not a native-device or live-provider test.

Apply migrations through `0080_retire_legacy_vocab` before releasing the updated
API and clients. `0079_learning_practice` adds the practice ledger; `0080` removes
the retired catalog, saved old/custom Learning entries, and their item history
for English and Spanish. Stop older API/workers before the retirement so they
cannot reseed old words. Seed the active catalog afterward; retained new IDs
preserve their progress. The data deletion is intentional and irreversible by
schema downgrade.

Physical-device speech, silent-switch behavior, background/recording transitions,
and opt-in push/email delivery remain release smoke checks. This review does
not deploy the app to production.
