# Learning content

`en.json` and `es.json` are the complete active lesson paths, validated by
`LessonPath` before use. English has 40 entries in four groups: conversation
expressions, phrasal verbs, idioms, and proverbs. Spanish has 20 idioms and
proverbs in two groups. The old beginner words and topic groups are retired.
Every entry has a full definition, classification, and at least two distinct,
natural examples in the target language.

Keep a retained chapter's `slug` and word's `content` stable: together with the
language they determine its UUID and connect it to saved progress. Changes to
that identity require an explicit content migration. Do not silently recreate
retired groups or use a legacy word bank as a fallback.

`vocabulary_kind` describes the unit (`word`, `expression`, `phrasal_verb`,
`idiom`, `proverb`). `verb_kind` and `noun_kind` classify the taught sense;
they are optional for other parts of speech. Examples may use natural inflected
forms. Never substitute an infinitive into a conjugated example.

Multiword entries use the pronunciation action without invented IPA.
Examples are structured arrays; the catalog adapter retains newline-separated
`example_sentence` for older API/database consumers.

Migration `0080_retire_legacy_vocab` freezes this release's keep set and deletes
retired catalog rows, saved old/custom words, and their practice history in
English and Spanish Learning classes. Runtime reconciliation enforces the active
catalog as well. Retained IDs keep their mastery, schedules, notes, and history;
class identity and daily goals survive. This intentional deletion cannot be
undone by downgrading the schema.

Content changes must pass catalog quality and reconciliation tests under
`app/tests/services`, plus PostgreSQL reconciliation and migration tests under
`app/tests/repositories`.
