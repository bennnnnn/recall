# Clarifying questions: a card the user answers with a tap

People rarely ask in full the first time ("how can I understand integrals?"). When the answer
depends on something only the user knows (their level, their goal, their budget), Recall asks
with a card of choices instead of a paragraph of questions. The user taps, presses **Submit**, and
the picks go back as their next message; Recall then answers with them in mind. Decided with the
user on 2026-10-22.

## When Recall asks

- **First, only when stuck.** If any answer would be a guess ("plan my week", "which laptop
  should I buy", "how can I understand x" with nothing about the person), the reply is one short
  sentence and the card; no answer yet.
- **After, to tailor.** If a good general answer exists, Recall answers it, and may put the card
  under the reply when the picks would change the answer in a real way ("Want this fitted to
  you?"). The picks bring a fuller, specific answer that restates the whole thing clearly, not a
  patch on the first one.
- **Never** for a plain fact, a sum or a solved STEM problem, a greeting, a reminder, a picture,
  a draft whose purpose was given, or a message that is merely garbled (that keeps its one-line
  "did you mean…?" reply, `prompt_constants/unclear.py`).
- One card per reply, 1 to 3 questions, 2 to 4 choices each. Memory, the chat so far and the
  question itself come first: Recall never asks what it already knows.

## The card

- Each question shows its choices; a question may allow several picks.
- Every question ends with **Other…**, which opens a short text field.
- **Submit** is enabled once every question has an answer. **Skip** sends "Just answer" (in
  the app's language) and Recall answers with its best general reading. Typing a normal
  message instead also skips. The server needs no word list for it: any message after a
  card that is not the picks gets the same hint (answer the request now, do not ask again;
  a new question is answered as asked).
- After Submit or Skip the card stays, read-only, with the picks ticked.

## What is sent

The picks are the user's next message, a normal bubble, one line per question:

```
Studied it before: No, never
What it's for: An exam next week
```

The phone writes it from the card (question label, then the picked choices or the typed text) in
the user's language. The server knows it answers the card because the previous assistant reply
holds the card; its prompt then says: answer the original request with these details, in full.

## The `clarify` fence

Written by the model, checked and normalised by the server before it is saved (Pydantic): a
card that breaks the rules is removed, and a "first" reply that is left with no question becomes
plain prose. JSON, one object:

```json
{
  "when": "first",
  "questions": [
    {"id": "level", "label": "Studied it before", "question": "Have you studied integrals before?",
     "options": ["No, never", "A little", "Yes, I'm revising"], "multi": false},
    {"id": "goal", "label": "What it's for", "question": "What do you need it for?",
     "options": ["An exam", "A class", "Curiosity"], "multi": false}
  ]
}
```

- `when` is `first` (no answer yet) or `after` (under an answer).
- `label` is the short name used in the sent message; `question` is what the card shows.
- Text is in the user's language; the phone adds Other…, Submit and Skip from i18n.
- In the chat history the model reads a card as one compact line ("Asked: Have you studied
  integrals before? [No, never / A little / Yes, I'm revising] …"), so the next message makes sense.

## Where it lives

| Part | Path |
|------|------|
| When to ask, the card's shape, the next turn's hints (prompt) | `apps/api/app/modules/chat/prompt_constants/clarify.py` |
| Check and normalise the fence (finalize pass `clarify_card`) | `apps/api/app/modules/chat/clarify_card.py`, `finalize_text.settle_clarify` |
| The card in history, and the turn after a card | `apps/api/app/modules/chat/clarify_turn.py` (read by `prompt_window.py`, `prompt_sections.py`, `turn_prep/mode.py`) |
| The card | `apps/mobile/components/rich/ClarifyCard.tsx` |
| The sent message, and a sent message read back onto its card | `apps/mobile/lib/clarify/clarifyCard.ts` |
| What the card reads from the chat: the send path, busy, newest reply, the answer | `apps/mobile/components/rich/clarifyContext.tsx`, provided by `features/chat/components/ChatReplyProviders.tsx` and `MessageBubble.tsx` |

On the phone a card is live only on the newest reply while nothing streams. Once answered it
stays read-only with the picks ticked, read back from the user message after it, so no store is
needed across list recycling or a restart. Copy and Read aloud give each question with its
choices.
