"""What each plan allows per day, per month or in total, and the global daily spend cap."""

from pydantic import BaseModel


class PlanAllowanceSettings(BaseModel):
    """One number per plan: ``<base>`` is free, ``<base>_pro`` the paid plan.

    ``modules/billing/entitlements.py`` (the one place plan policy lives) reads
    them by that name. 0 = not part of that plan; None = no cap of its own (Pro's
    messages; read-aloud, which the token budget meters instead). A new allowance
    is two fields here and one ``Allowance`` entry there. Owner's limits,
    2026-11-24: Free counts only its messages; Pro's are below.
    """

    # The allowances a plan counts as part of its messages: no daily slots of their
    # own. A photo or file may be uploaded while the account has a message left today
    # (the send takes the message); a turn's search or photo lookup, and a sent scanned
    # PDF's OCR, are covered by that turn's message, and at most one search per turn
    # reaches the providers (``web_search.TurnTavilyBudget``). A plan's cap below for
    # an allowance listed here is unused.
    follow_messages: list[str] = [
        "daily_image_uploads",
        "daily_document_uploads",
        "daily_web_searches",
        "daily_image_searches",
        "daily_scanned_documents",
    ]
    # Pro's photos only: its messages are unlimited, so its photo uploads are bounded by
    # file size, the Library total and the request limits.
    follow_messages_pro: list[str] = ["daily_image_uploads"]
    # Daily image uploads (per user, UTC day), enforced at presign: on a plan that does
    # not list them in ``follow_messages``.
    daily_image_limit: int = 10
    daily_image_limit_pro: int = 30
    # Daily document (PDF, Word, text) uploads: each is read and parsed on the API
    # machine. Also enforced at presign.
    daily_document_limit: int = 10
    daily_document_limit_pro: int = 100
    # Scanned PDFs read by vision OCR a day (up to ``ATTACHMENT_OCR_INDEX_MAX_PAGES`` calls
    # each), counted per file the index job reads: a resend's copy of a file counts again,
    # since it is read again. Free's follow its messages.
    daily_scanned_document_limit: int = 10
    daily_scanned_document_limit_pro: int = 100
    # Tavily searches per user per UTC day. Past the cap a turn gets no search at all
    # (the reply says today's searches are used up); DuckDuckGo stands in only when
    # Tavily itself fails.
    daily_tavily_searches: int = 10
    daily_tavily_searches_pro: int = 40
    # Voice input per UTC day. Read-aloud has no count of its own: each request is
    # charged to the day's token budget by its text's length (``speech/tts_tokens``);
    # 0 leaves it out of a plan.
    daily_speech_transcriptions: int = 0
    daily_speech_transcriptions_pro: int = 100
    daily_speech_tts: int | None = 0
    daily_speech_tts_pro: int | None = None
    # Live talk minutes per UTC calendar month.
    monthly_live_talk_minutes: int = 0
    monthly_live_talk_minutes_pro: int = 60
    # AI pictures and reference-photo lookups per UTC day.
    daily_image_generations: int = 3
    daily_image_generations_pro: int = 30
    daily_image_searches: int = 10
    daily_image_searches_pro: int = 30
    # Bytes one account may keep in its Library at once (every attachment row:
    # uploads, the copies a resend makes, generated pictures and reference photos).
    # Checked at presign: with the per-minute request limits, this is what bounds
    # uploads that are never sent.
    library_storage_bytes: int = 400 * 1024**2
    library_storage_bytes_pro: int = 4 * 1024**3

    # Auto's everyday turns on the stronger model (``ROUTING.everyday_strong``), not
    # the cheap one (``ROUTING.everyday``). Hard and maths turns route as before.
    strong_everyday_model: bool = False
    strong_everyday_model_pro: bool = True

    # Chat messages per UTC day: what each plan offers and the meter shows. A turn's
    # prompt (rules, memory, history) cost about 10k tokens, so a token allowance gave
    # Free about ten messages and the paid plan about fifty (audit, 2026-11-06). None is
    # no daily cap: Pro's chat is unlimited (owner, 2026-11-24), its token guard behind it.
    daily_message_limit: int | None = 10
    daily_message_limit_pro: int | None = None
    # Chat tokens per UTC day: a cost guardrail behind the message allowance, set well
    # above what the plan's messages use, so only a runaway account meets it (on an
    # unlimited plan, the only daily stop).
    daily_token_limit: int = 400_000
    daily_token_limit_pro: int = 15_000_000
    # UTC-day OpenRouter spend ceiling (foreground + background). 0 = unlimited
    # (dev/tests). Production boot requires a positive value.
    daily_global_spend_usd: float = 0.0
