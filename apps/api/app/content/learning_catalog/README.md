# Learning content

`en.json` and `es.json` are the active lesson paths, validated by `LessonPath`
before use. English has 20 groups and 387 entries; Spanish has 43 groups and
519 entries. Each taught sense has a definition, part of speech, classification,
and at least two distinct examples in the target language. Topic groups keep
related vocabulary together; later groups introduce expressions, phrasal verbs
(English), idioms, and proverbs.

Keep an existing chapter's `slug` and a word's `content` stable: together with
the language they determine its UUID and connect the lesson to saved progress.
Do not reorder existing chapters or move words between them as a content edit.
Append new groups. Separate Spanish chapters may intentionally teach different
senses of the same word, such as `hogar` for household and dwelling.

`vocabulary_kind` describes the unit (`word`, `expression`, `phrasal_verb`,
`idiom`, `proverb`). `verb_kind` and `noun_kind` classify the taught sense;
they are optional for other parts of speech. Examples may use natural inflected
forms. A lesson must never substitute an infinitive into a conjugated example.

Existing verified IPA and short glosses remain. New multiword groups use the
pronunciation action without an invented IPA transcription. Examples are
structured arrays here; the catalog adapter retains newline-separated
`example_sentence` for older API/database consumers.

The Python `vocab_banks_en` and `vocab_banks_es` modules retain historical
catalog identities and original content fingerprints. They support saved
Hotel/SAT references and safe adoption of known older lesson rows. They are
not the active lesson editor. Catalog reconciliation updates only content,
preserving user item IDs, practice history, mastery, scheduling, and notes.

Content changes must pass the catalog quality/identity tests and reconciliation
tests under `app/tests/services`, plus PostgreSQL reconciliation tests under
`app/tests/repositories`.
