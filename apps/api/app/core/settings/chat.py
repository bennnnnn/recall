"""What a chat turn's prompt carries: recent window, history compression and RAG, to-dos."""

from pydantic import BaseModel


class ChatContextSettings(BaseModel):
    # Chat-history semantic RAG (pgvector over past turns; top-k at turn start).
    # Never dumps the full transcript — Golden Rule 3. Recent-window ids are
    # excluded so this complements memory + summary, not duplicates them.
    chat_history_rag_enabled: bool = True
    chat_history_rag_chunk_limit: int = 6
    chat_history_rag_min_similarity: float = 0.30
    chat_history_rag_chunk_chars: int = 900
    chat_history_rag_chunk_overlap: int = 120
    chat_history_rag_max_chunks_per_message: int = 6
    # A search ranks the user's newest chunks only (exactly, no vector index); older
    # chunks are deleted as new ones are stored (``chunks_repository.prune_beyond_window``).
    chat_history_rag_search_window: int = 2000
    # The chat's last rows a turn's readers see (the live read, follow-ups, lesson and
    # chart readers, the turn mode). The prompt's own history is the ``history_*`` below.
    recent_message_window: int = 20
    link_preview_cache_ttl: int = 3600
    todo_inject_limit: int = 100
    # A reminder change from chat is a card the user taps to save (or mark
    # done, move, delete). Off: chat writes to-dos as soon as it reads them.
    todo_prompt_limit: int = 48

    # History compression. The prompt carries every message after the summary's edge
    # verbatim, up to ``context_token_budget`` tokens and ``history_max_messages`` rows; the
    # compress job folds the oldest into the summary only once they pass the trigger, and
    # then back to the target. Between folds a turn's prompt starts as the last one did, so
    # a provider's prefix cache serves it: a window that slid by one message every turn
    # changed the prompt right after the rules, and no history was ever a cache hit.
    # ``context_cache_eval sim`` (2026-11-22): the owner's 80-message chat kept 20 rows
    # (1.9k tokens) at 20/16k, 39 rows here; cacheable 48% → 85%, the chat's input cost at
    # a cached price of 25% $0.094 → $0.056. At 6000 a chat building an HTML page kept only
    # its last version (each ~5,900 tokens, 2026-10-29); 32000 keeps about five. Every model
    # alias reads 128k or more. Over the budget (a fold still running, a long paste) the
    # prompt slides: the newest rows the budget keeps and the unsummarized gap before them.
    history_compression_enabled: bool = True
    context_token_budget: int = 32_000
    history_max_messages: int = 80
    history_fold_trigger_tokens: int = 24_000
    history_fold_trigger_messages: int = 64
    history_fold_target_tokens: int = 12_000
    history_fold_target_messages: int = 24
    summary_max_tokens: int = 800

    # "Draw it", "show it": a fast model reads which earlier message "it" is
    # (``chat.referent_read``). Off, or no answer in time, and the turn reads the line
    # as before. Foreground: kept short, no retry.
    referent_read_enabled: bool = True
    referent_read_timeout_seconds: float = 2.0

    # Claim check — on a searched reply, a claim the sources and the user's messages do not
    # support is cut before it saves (``modules/chat/claim_check.py``). Off: replies as written.
    claim_check_enabled: bool = True
    claim_check_timeout_seconds: float = 8.0
    # A short reply is only read for its source chips, and `done` waits on it: past this,
    # every chip stays. Live short checks took at most 2.4 s (2026-11-10).
    claim_check_short_timeout_seconds: float = 2.5

    # Lesson shape — a lesson reply ends with its title and practice card, and a teach-me
    # outline lists its topics and ends on its question; what the model left out is added
    # before it saves (``modules/chat/lesson_shape.py``). Off: replies as written.
    lesson_shape_enabled: bool = True
    lesson_shape_timeout_seconds: float = 10.0
