"""Uploaded files: extraction, OCR, attachment RAG, the orphan reaper and object storage."""

from pydantic import BaseModel


class AttachmentSettings(BaseModel):
    attachments_enabled: bool = True
    # PDF/DOCX text extraction is sync, CPU-bound parsing; it runs on a worker
    # thread (like the SymPy math solve) bounded by this timeout so a large or
    # adversarially crafted file can't block the event loop.
    attachment_extract_timeout_seconds: float = 5.0
    # Image-only / photographed PDFs have no text layer. After the fast
    # pypdf extract returns empty, render pages (pypdfium2) and transcribe
    # via vision-chat. Separate budget — vision is network, not the 5s CPU
    # extract timeout. Same excerpt + chunk/RAG path; no second pipeline.
    attachment_ocr_enabled: bool = True
    attachment_ocr_max_pages: int = 6
    # Index job only — vision cost, not 500 text-layer pages.
    attachment_ocr_index_max_pages: int = 20
    attachment_ocr_timeout_seconds: float = 30.0
    attachment_ocr_index_timeout_seconds: float = 120.0
    attachment_ocr_page_timeout_seconds: float = 12.0
    attachment_ocr_render_scale: float = 1.5
    # Pixel budget per rendered PDF page. The scale above applied to any page
    # size, so a 435-byte PDF with one 14400x14400 pt page rendered a ~2 GB
    # bitmap (5.1 GB peak RSS locally) on a 512 MB machine. Oversized pages
    # are scaled down to this budget; a letter page at 1.5x is ~1.1 MP.
    attachment_ocr_max_page_pixels: int = 4_000_000
    # Largest image (pixels actually decoded) a gallery thumbnail will decode.
    # JPEG decodes at a reduced scale first, so big photos still work; a
    # lossless image past this is refused (422) instead of decoding hundreds
    # of MB from a sub-MB file. 0 disables.
    attachment_image_max_decode_pixels: int = 16_000_000

    # Attachment RAG (chunk + embed PDF/doc text; retrieve into prompt).
    attachment_rag_enabled: bool = True
    attachment_rag_chunk_limit: int = 6
    attachment_rag_min_similarity: float = 0.25
    attachment_rag_chunk_chars: int = 900
    attachment_rag_chunk_overlap: int = 120
    attachment_rag_max_chunks_per_file: int = 256
    # Per-image token reserve added to the quota reservation for vision turns,
    # so a near-limit user can't start a heavy image call that blows past the
    # daily cap. Real usage is still reconciled from the provider's usage chunk.
    image_attachment_reserve_tokens: int = 1200
    # Orphan attachment reaper: hidden send-clones (library_visible false)
    # stay until this billed window. Unverified original uploads use the
    # shorter pending window so a killed-app image slot can refund same-day.
    attachment_orphan_grace_hours: int = 24
    attachment_pending_orphan_hours: int = 1
    attachment_orphan_reaper_interval_seconds: int = 3600
    # Bounded reaper batch — the scheduler re-runs, so a limit drains over time
    # instead of loading every orphan in the system into memory.
    attachment_orphan_reap_limit: int = 100

    # Object storage for attachments. ``local`` writes to disk (dev);
    # ``r2`` presigns Cloudflare R2 (S3-compatible) URLs so the client uploads/
    # downloads directly — blobs never touch the API. R2 creds come from the
    # r2_* settings below; when missing in dev we fall back to local.
    storage_backend: str = "local"
    # Home dir, not /tmp: macOS purges /tmp (and Neon rows then 404 on /file).
    storage_local_path: str = "~/.recall/attachments"
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    r2_endpoint: str = ""  # derived from account_id if empty
    r2_presign_expiry_seconds: int = 600
    # boto3 defaults are 60s connect + 60s read with 5 legacy attempts, all on
    # the default thread pool (5 threads on one CPU) shared with sign-in and
    # PDF extraction. Bounded here; "standard" retries back off with jitter.
    r2_connect_timeout_seconds: float = 5.0
    r2_read_timeout_seconds: float = 20.0
    r2_max_attempts: int = 3
