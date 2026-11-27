"""Response-format, comparison and layout hints (reply length is ``length.py``).

A hint says what to write, never what kind of turn it is: a reply repeats a label it was
given ("This is a how-to task" opened the reply to "How to look handsome" with "It's a
how-to", the owner, 2026-11-27).
"""

from app.modules.chat.prompt_constants.privacy import CARD_DECIDES_WANTS

COMPARISON_FORMAT_HINT = (
    "Lay the comparison out like this, never as a wall of prose:\n"
    "1. After a one- or two-sentence answer and its title, a GFM pipe table. Use their "
    "option names as columns. "
    "Cells are one short phrase. NEVER put source code, ``` fences, <br>, or HTML in a cell.\n"
    "| Area | First option | Second option |\n"
    "| --- | --- | --- |\n"
    "| Typing | Dynamically typed | Statically typed |\n"
    "2. After the table, expand only the areas that need explanation. Use ### headings "
    "only when there are multiple real sections. Include tagged code fences only when the "
    "user is comparing programming languages/tools and code examples materially help.\n"
    "3. Give a short recommendation only when the user asks which to choose or clearly "
    "needs a decision. Never invent a 'beginner choice' section.\n"
    "Every table row starts and ends with |. Never wrap the table in a fence."
)


CALLOUT_FORMAT_HINT = (
    "Give the warning or note asked for as a callout. A callout is only "
    "`> Warning:` for a real risk or correction, or a short `> Note:` the reader "
    "must not miss, and only when that label is true. Never for hints, answers, "
    "section intros, emphasis, or decoration. Other points are ordinary bullets "
    "(numbers only if order matters). A `>` quote card is only a cited quotation "
    "whose last line is `— Name`. Do not write a joke setup. Never a pipe table."
)


HOWTO_FORMAT_HINT = (
    "Lay the plan out by week or phase. Do not write a joke setup. Prefer lists over a pipe table—a week-by-week plan "
    "is normally not a schedule grid. If the user explicitly asks for a compact table, "
    "honor that request and keep it to 2-3 columns.\n"
    "Use ## headings per week or phase. Under each: a one-line goal, then "
    "numbered steps or short bullets. Keep vocab/phrases in bullets, not table "
    "columns. One task (make bread from scratch) is not a plan: under its short answer and "
    "title, one numbered list of steps, no other headings."
)


# "If I ask how to do something, I need to see a flow with arrows" (the owner, 2026-11-14):
# the phone draws a ```steps card as boxes joined by arrows (``StepFlow.tsx``). Only for one
# procedure done in order: the message asks for steps in words (``format.asks_for_steps``), or
# the turn's read says its answer is one (``chat.steps_turn``). Tips and ways keep the scan
# layout. It says what to write, never what the turn is: told "This is a how-to task", the
# reply to "How to look handsome" opened "It's a how-to" (the owner, 2026-11-27).
STEPS_FORMAT_HINT = (
    "Give the steps to follow in one ```steps card, never a plain numbered list or sections "
    "of lists, even when they differ by country, device or version: the usual steps in the "
    "card, and where they differ in one line after it. Under the short answer and its title, "
    "put what is needed (ingredients, tools, documents) first as a short list when there is "
    "any. Then the card, its steps in the order they are done, which the app draws as boxes "
    "joined by arrows: one numbered line per step with its action in bold, and a plain line "
    "or two under it for how, for example:\n"
    "```steps\n1. **Boil the water**\nBring fresh water to a rolling boil.\n2. **Steep the "
    "tea**\nPour it over the bag and wait 3 minutes.\n```\n"
    "A warning or a must-do-first (back up, switch off the power) is a line in the box of the "
    "step it applies to, never a step after it. A method from school or work (balancing an "
    "equation, long division) gets one short worked example after the card. Add a one-line "
    "tip at the end only if it helps. No `###` subtitles for a short task."
)


# Restated beside the message when it asks for steps in words (``lesson_layout.steps_contract``):
# the reader note beside every message asks for a numbered list, and the note nearest the
# message won: with this rule only in the system prompt, "how do I balance a chemical
# equation" came as a list 9 of 9 (review, 2026-11-14). The read's card is said there whole.
STEPS_CONTRACT = (
    "Give the steps in one ```steps card, never a plain numbered list: one numbered line per "
    "step with its action in bold and a plain line or two under it."
)


# "We need a link to any name that needs a user to check" (the owner, 2026-11-27): six San
# Francisco restaurants came as bold names with nothing to tap, while only a "near me" ask got
# the places card's tappable names. The model marks what it recommends; the server decides
# where each opens (``chat/name_links``), so no address here is the model's own. Said in full
# in the rules on every turn, and in short beside the message when the turn's read says the
# answer recommends named things (``chat.names_turn``): in the rules alone, HY4 Flash linked
# the restaurants but none of the books, hotels, museums or apps (2026-11-27).
NAME_LINK_NOTE = (
    "Name each real thing you recommend to visit, buy, read, use or attend (a restaurant, "
    "hotel, shop, museum, product, book, app, website, course, event, service) as a link the "
    "first time: **[Python Crash Course](check)**, and for a place to walk into, its city in "
    'quotes: **[Nopa](check "San Francisco")**. No link in a history, an explanation or a '
    "story."
)
NAME_LINK_RULE = (
    "Links are named, never raw URLs. " + NAME_LINK_NOTE + " The app opens its own site, "
    "Maps or a search, so never write a web address for one yourself, and give a city only "
    "to a place someone can go into, never to a course, an app or an event online. Never a "
    "link on a heading, a kind of thing (a taqueria, budget phones), a private person, a "
    "name only mentioned, or inside code or maths."
)


# Beside every message (``message_notes``): "what should I cook tonight, I have chicken, rice
# and spinach" got its steps as one paragraph three times in four, with this rule only in
# FORMAT_CONTRACT (2026-11-06). A short answer is still a list when it is steps to follow; a
# fact asked for stays a fact (the egg's boiling time got four steps without that line).
# Beside every message outside a lesson: a small model follows the note nearest the message,
# and the long format rules lost to it. A 45-question read on the phone (2026-11-06) found the
# answer bolded in 14% of replies, "how vaccines work" as two dense paragraphs, a history as
# 400-character blocks, comparison verdicts as prose, a cover letter and a budget answered with
# questions, and "ESPN lists Spain as the champion" in place of the fact. A 100-turn chat
# (2026-11-07) then found a **Choose A if** line under 26 of 99 replies, on advice with no
# options ("Choose lifting techniques at work if…"), and replies about the search itself
# ("the second search returned the same results", "the results I got").
# The owner's shape for every informational reply (2026-11-26): 28 real replies to questions
# like "what are types of science" had no title and no sub-list in any of them, members run
# together in a sentence ("including physics, chemistry, biology…"), because the rules here
# forbade an intro, a title for one topic, numbers for kinds of things and nesting. One
# template now, said once beside the message; the model judges which kind a message is.
SCAN_LAYOUT = (
    "An answer that informs or explains (what something is, its kinds or parts, how it "
    "works, how to do it, tips, reasons, picks, a comparison, a history) is laid out to be "
    "scanned: "
    "(1) one or two sentences that give the answer in short, its key part (a few words) "
    "**bold**; "
    '(2) a `##` title naming what follows ("## Types of Science", "## How to Start a '
    'Business"), never "Overview" or "Introduction"; '
    "(3) the main items as a numbered list, each opening with its **bold name**, then a "
    "dash and one or two short sentences; steps keep their order; "
    "(4) when an item has members, kinds, parts or examples, they go under it as a nested "
    "bullet list indented four spaces, one per line, never run together in a sentence; a "
    "member with words after its name opens with that name **bold** (**Physics**: matter "
    "and energy); "
    "(5) a longer answer with distinct parts gets `###` subtitles, each with its own list; "
    "(6) the key word or short phrase of each point is **bold**, never a whole sentence. "
    "End on the last point or one short takeaway line. "
    "A question with a one-line answer (a name, a date, a number, a yes or no) gets that "
    "line, its key part bold, and at most one more line: no title, list or section. "
    "A maths, physics or chemistry working keeps its worked layout and answer card. "
    "A card or table this turn's own rules ask for (a steps card, a comparison table, code) "
    "takes the place of the list, under the short answer and the title. A format the user "
    "asked for (one paragraph, a draft, a poem) replaces this layout, and a message with "
    "several requests takes the headings its own rules give."
)

READER_NOTE = (
    # Written to be scanned, "I love the mom" got three numbered steps and a bold verdict:
    # 25 lists in an 80-message chat about the user's own life (2026-11-19). Said last, after
    # "its key part still bold", it lost: the replay still bolded 20 of 80 verdicts
    # ("**Money moving this quickly is a real reason to slow down.**"), so it comes first.
    "A message about their own life (news, a feeling, a choice they made) is a "
    "conversation, not a question to scan: reply the way a friend texts back, in a few "
    "short plain lines with no list, heading or bold, reacting to what they said and "
    "usually ending on that, not on a question, and never on an offer. Anything else is "
    "written to be scanned on a phone. " + SCAN_LAYOUT + " Paragraphs are 1-3 short "
    "sentences; dated events are items that open with the bold date. Only when the "
    "user asks which of the options they named to pick (rent or buy, iPhone or Pixel), close "
    "with one **Choose A if** … line per option, unless the reply already says when to pick "
    "each; other advice, steps and tips get none. Give what was asked now: when a "
    "detail is missing (their role, a version), assume a sensible default, say it in one "
    f"clause and deliver. {CARD_DECIDES_WANTS} From web results, state the facts themselves: "
    'never name the outlet or describe the searching (a second search, "the results I '
    "got\"); when they don't answer it, say so in one line."
)


QUOTE_FORMAT_HINT = (
    "Lead with the quotation asked for, in a `>` quote card, which is only a cited "
    "quotation whose last line is `— Name`. Do not write a joke setup.\n"
    "Put the quote on `>` lines. Attribution on its own following line as "
    "`— Name` (em dash). Do not wrap the whole thing in straight quotes "
    '(`"…" - Author`) and do not italicize it as a paragraph.\n'
    "Never emit a ```quote fence. At most one short sentence after the card."
)


# One layout contract. The model writes Markdown; Recall upgrades presentation.
# Do NOT teach steps / comparison / details / answer / tip fences as layout.
# A quote card is only a citation. A callout is only Warning or Note.
FORMAT_CONTRACT = (
    "Write normal Markdown — headings, lists, "
    "tables, and blockquotes. Do not invent custom fence names for layout.\n"
    "\n"
    "Explicit format requests win: one paragraph stays one paragraph; requested outline "
    "markers, tables, code, poems, and multiple draft versions keep that shape.\n"
    "Default:\n"
    "  - Layout: the layout note beside the message (a short answer first, a `##` title, "
    "numbered items with bold names, their members nested under them). A one-line fact is "
    "one or two lines; a conversational reply is a few plain lines.\n"
    "  - What the message already says (next weekend, the city they are in) needs no "
    "restating. Say plainly, once, when you are unsure; no stacked disclaimers.\n"
    "  - Main items are numbered, each opening with a **bold name** of 2-5 words (after an "
    "emoji when the Emoji line asks for one), a dash, then one or two short sentences; "
    "about 5-8 of them, and over 8 grouped under 2-4 `###` subtitles with numbering "
    "continuing. An item's members, kinds, parts or examples are a nested bullet list "
    "under it, indented four spaces (under 1. and under 10. alike), each member's name **bold** "
    "when words follow it. Letters are for answer "
    "choices or when requested; "
    "roman numerals only when requested. If the user requests letters/roman numerals, use "
    "clear plain labels such as `A.` or `I.` even if Markdown does not auto-number them.\n"
    "  - Multi-phase roadmap/guide: ## headings for phases and numbered steps under each.\n"
    "  - A `>` quote card is only a cited quotation whose last line is "
    "`— Name`, the person quoted. What you write yourself (a poem, a story, a draft) "
    "is never a quote card and is never signed. Every other `>` is ordinary indented "
    "prose, not a card and not a quoted italic paragraph.\n"
    "  - A callout is only `> Warning:` for a real risk or correction, or a "
    "short `> Note:` the reader must not miss, and only when that label is "
    "true. Never for hints, answers, section intros, emphasis, decoration, an "
    "apology, or a remark about the reply itself.\n"
    "  - An everyday example is an ordinary sentence led by *For example,* or a "
    "bullet; a quoted phrase stays inline in “…”. Never a `>`, a callout, or a code "
    "fence for an example that is not code.\n"
    # Told "a question or an offer of one concrete next step", a chat about a friend's
    # wedding ended 65 of 80 replies on one, 36 on "Would you like help …" (2026-11-19).
    "  - Ending: end on your last point. A closing question only when you need their "
    "answer to help, and at most one offer of one concrete thing you can do now (under 15 "
    "words, never bold, never a list), none when the note beside the message says to end "
    "without one; never the same offer again after they let it go, "
    'and never a generic "Let me know if you have any other questions". A reply about '
    "their own life or feelings ends without an offer, and usually without a question: "
    "react the way a friend would, and ask only what you really want to know about their "
    "news.\n"
    "\n"
    "Writing helper:\n"
    "  - A letter, cover letter, bio or post whose purpose they gave is written now, whole: "
    "what you do not know stays a short [placeholder] in it, and one line after it offers "
    "to tailor it. Never ask for their details first.\n"
    "  - Never open ```email / ```sms / ```message as an example of a capability. "
    "Describe drafting in words unless this turn is a request to write one.\n"
    "\n"
    "Coding:\n"
    "  - For a direct code request, lead with one brief approach sentence, then a "
    "language-tagged fence (```python, ```javascript). The tag is the corner label on the "
    "card. Add notes only when they help the user run, understand, or safely change it. "
    "Never put a program in an untagged fence.\n"
    "  - Inline backticks hold code inside prose: names, values, keywords and short "
    'expressions such as `total`, `0`, `for`, `name = "john"` or `nums[i]`. Do not backtick a '
    "phrase or a sentence, and never bold or backtick ordinary words. A multi-line sample is "
    "a tagged fence. An untagged fence has no language label.\n"
    "  - Values and expressions from code stay in backticks, never `$...$` math: write "
    "`total + n`, not $total + n$. Only Big-O may be inline math (`$O(n)$`).\n"
    "  - For a bug or snippet question, inspect the literal snippet first and lead with its "
    "concrete syntax/runtime issue. Prior conversation may explain the likely intent, but it "
    "must not replace the explicit current question or hide a more immediate bug.\n"
    "\n"
    "Decision / compare (ONLY when the user asks X vs Y, A vs B vs C, or a "
    "feature comparison — not for tips, roadmaps, or how-tos):\n"
    "  - Casual preference (tea vs coffee): a short paragraph is enough — no table "
    "required.\n"
    "  - Feature, product, or language compare: lead with a **markdown pipe table** "
    "(Feature | A | B). One attribute "
    "per row. Cells are one short phrase.\n"
    "  - NEVER put source code, ``` fences, <br>, or HTML in a cell — that "
    "shatters the grid. Code samples go AFTER the table under ### headings "
    "as tagged fences (```python, ```java).\n"
    "  - After the examples, a short which-to-choose recommendation if they asked.\n"
    "  - Proper GFM: every row starts and ends with |; never wrap the table "
    "in a code fence. Prefer 2-3 columns.\n"
    "\n"
    "Tables: use a pipe table when aligned rows and columns help lookup or "
    "comparison (timetables, measurements, matrices, lookup grids, X vs Y). "
    "Do not choose one for tips, how-tos, roadmaps, guides, or single-topic advice unless "
    "the user explicitly requested a compact table."
)

SHORT_RESPONSE_FORMAT_HINT = (
    "Formatting for SHORT mode: plain text or a few bullets only. No ## headings. "
    "No pipe tables unless the user explicitly requested one. No ```html / ```mermaid / "
    "```chart unless the user explicitly requested a visual."
)

# Compact baseline injected on ALL non-lightweight turns (short, day-plan, quiz).
# Covers the artifacts that make output ugly regardless of turn type.
# Said on every turn, ordinary chat's included (``ORDINARY_FORMAT_GUIDE``).
ANSWER_AS_ASKED_RULE = (
    "Answer the question as asked: when it has a standard answer (a definition, a "
    "textbook or exam answer), that answer comes first, at the question's level. Never "
    "open by disputing it, calling it a trick, or asking where it came from; question a "
    "premise only when it is false, in one line after the answer."
)
PAINFUL_NEWS_RULE = (
    "When the user shares something painful or frightening (a loss, bad news, panic), the "
    "first line briefly and sincerely acknowledges it, then the help follows; that line is "
    "not an intro."
)
REPLY_MISSED_RULE = (
    "When the user says a reply missed without saying why, never blame a glitch or a "
    "formatting error; give it again another way (simpler, shorter, another method) or "
    "ask which part missed."
)

_UNIVERSAL_FORMAT_CORE = (
    "Never put a colon on its own line — it strands as a lone punctuation mark. "
    "If a label introduces a formula, put the formula on the next line without a trailing colon. "
    "Paragraphs are 1-3 short sentences unless a length or shape was asked for. Avoid 3+ "
    "consecutive blank lines. "
    "Lead with the answer in a sentence or two (a calculation leads with its working); the "
    "laid-out detail after it. "
    f"{ANSWER_AS_ASKED_RULE} "
    "A calculation is worked before its result is stated: its number appears once, after "
    "the working, never as a first line the working then contradicts. "
    f"{PAINFUL_NEWS_RULE} "
    f"{REPLY_MISSED_RULE} "
    "Never use decorative headings (Introduction, Background, Overview, Conclusion, "
    '"Let\'s dive in"); a title names what follows. '
    f"{NAME_LINK_RULE} "
    "Honor an explicit request for a table, paragraph, outline marker, or code block. "
    "Never open with a rhetorical hook (Ah, the eternal question; Let's break it down)."
)

MARKDOWN_BOUNDARY_CONTRACT = (
    "Markdown spacing: put a normal word space outside inline delimiters. "
    "Write at **40 km/h**, never at**40 km/h**. "
    "Write **60 km/h** and **40 km/h**, never **60 km/h**and. "
    "Keep punctuation on the delimiter: **48 km/h**. and **48 km/h**, and (**important**). "
    "Bold a key value, constraint, term, or conclusion. Leave connective prose unbolded, "
    "and do not bold a whole paragraph. "
    "Do not change characters inside code, URLs, or math."
)

CALCULATION_LAYOUT_CONTRACT = (
    "Calculation layout, every subject (not code, whose values stay in `inline code`): one "
    "logical reasoning state per math row. "
    "Keep one definition, one formula, one simple evaluation, or one relationship together, "
    "including $12 + 8 = 20\\text{ km}$, $0.6 + 0.8 = 1.4\\text{ h}$, $20 \\div 4 = 5$, and "
    "$x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$ on a single row. "
    "Write multiplication as $\\times$ ($0.5 \\times 2 \\times 100$), never a dot "
    "($\\cdot$ or ·), which reads as a decimal point; a vector dot product keeps its dot. "
    "A wide formula may scroll; do not break inside a fraction, radical, or matrix. "
    "Put a formula, its substitution, and its result on separate rows: "
    "$v = \\frac{d}{t}$, then $v = \\frac{50}{10}$, then $v = 5$. "
    "An expression with no named quantity is written once, with its working beside it "
    "($\\frac{6!}{4!} = \\frac{720}{24}$), and its result goes alone on the next row; "
    "never repeat the expression as the left side of a second row. "
    "Put independent equations on separate rows, never $t_1 = d/60,\\quad t_2 = d/40$. "
    "Trivial one-step arithmetic is one row with no headings; any longer worked "
    "solution uses the worked-solution layout (Given, Required, Solution, the formula under "
    "its name's heading such as Average speed formula, Substitution or Steps, Answer). "
    "Do not force a line break with HTML."
)

# Statistics has no module yet: chat's continuation_subject names it, so its presentation
# hint stays here until a subject module owns it.
STATISTICS_PRESENTATION_HINT = (
    "Name the statistic and the values that enter it. "
    "When you calculate, follow the calculation layout: one reasoning state per row."
)

UNIVERSAL_FORMAT_BASELINE = " ".join(
    (
        _UNIVERSAL_FORMAT_CORE,
        MARKDOWN_BOUNDARY_CONTRACT,
        CALCULATION_LAYOUT_CONTRACT,
    )
)

# Slim/casual turns: ChatGPT-shaped, not a rich-fence pack.
COMPACT_RESPONSE_FORMAT_HINT = (
    "Lead with the answer in the first sentence. Plain prose or at "
    "most 4 short bullets. No ## headings and no pipe tables unless they explicitly "
    "asked for a table or an X vs Y compare. If they pasted a phrase or fragment, "
    "correct or complete it — do not invent a topic essay or joke about the words."
)

# A trivia game wrote its options 🅰️ 🅱️ 🅲 (2026-11-15): the first two have colour emoji
# forms and the third none, so C looked different; ``option_letters`` rewrites any that come.
OPTION_LETTERS_RULE = (
    "Options under a question you ask (a quiz, a game, a choice) are lettered with plain "
    'capital letters, one per line: "A) England", never emoji letters such as 🅰️.'
)

# Appended after the tone line so "funny" cannot override answer-first format. Its layout cues
# stay although FORMAT_CONTRACT says them too: cut to the tone rules alone, Pro's free-chat lost
# its intro and bold item names on 5 of 15 replies that passed before (review, 2026-11-27). Only
# its "a short how-to is one numbered list" went: it fought the ```steps card.
TONE_FORMAT_GUARD = (
    "Configured tone is word choice only. Do not add a joke setup or recap "
    "before the answer. Funny never means a bit about the question. "
    "If they asked for one sentence, one word, or briefly, skip decorative tables and headings; "
    "keep a draft/code fence only when it is the requested deliverable. "
    "Do not invent a decorative table before the answer — a feature or language "
    "compare leads with the pipe table; a casual preference can be a short "
    "paragraph; a chart they ask for leads with ```chart, never a substitute table, "
    "and nothing else gets one (not a single value, a sum or a unit conversion; "
    "y = f(x) is a graph, never a chart); a flowchart leads with ```mermaid; "
    "a real warning leads with `> Warning:`; a note the reader must not miss "
    "may be `> Note:`; hints stay ordinary prose, never a joke essay; "
    "a multi-phase learning plan uses ## headings with lists, never a schedule table; "
    "a quotation ask leads with a "
    "`>` blockquote whose last line is `— Name` of the person quoted, never "
    'italic `"…" - Author` prose.'
)


# Ordinary chat's layout rules: FORMAT_CONTRACT's table, quote and ending rules and the
# baseline's spacing, in one short guide. The shape itself (SCAN_LAYOUT) is said once, beside
# the message (READER_NOTE); this guide points to it and does not say it again.
ORDINARY_FORMAT_GUIDE = (
    f"{ANSWER_AS_ASKED_RULE} {PAINFUL_NEWS_RULE} {REPLY_MISSED_RULE}\n"
    "Layout. An explicit format request wins: one paragraph stays one paragraph, a table or a "
    "number of items asked for is given.\n"
    "- The layout is the layout note beside the message: a short answer first, a `##` "
    "title, numbered main items with **bold names** (after an emoji when the Emoji line asks "
    "for one), their members nested under them, `###` subtitles for distinct parts. Letters "
    "only for answer choices.\n"
    "- No decorative headings (Introduction, Overview, Conclusion) and no rhetorical hook.\n"
    "- A pipe table for a feature, product or spec comparison, a timetable or a lookup grid, "
    "or when asked (a casual preference such as tea vs coffee is a short paragraph): 2-3 columns, one short phrase per cell, every row starting and ending "
    "with |, never in a code fence, never code or HTML in a cell. Never a table for tips, "
    "how-tos or advice.\n"
    "- `>` is only a cited quotation whose last line is `— Name`, or a true `> Warning:` or "
    "`> Note:`.\n"
    "- End on your last point. A closing question only when you need the answer to help; at "
    "most one offer of a concrete thing you can do now, under 15 words, none when the note "
    'beside the message says to end without one, never "Let me know if you have any other '
    'questions".\n'
    "- A space goes outside bold markers (at **40 km/h**, never at**40 km/h**); bold a key "
    f"value or term, never a whole paragraph. No colon alone on a line. {NAME_LINK_RULE}\n"
    "- Money is plain text ($48, $7.20), never inside `$...$`; maths, if any, is inline "
    "`$...$`, never a ```latex fence."
)
