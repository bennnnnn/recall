"""Attachments — upload, extract, retrieve and reap user files.

``upload`` presigns and creates the pending row, ``content`` enforces the MIME
allowlist and extracts text, ``ocr`` covers image-only PDFs, ``rag`` chunks and
embeds that text for prompt retrieval, ``reuse`` copies a Library file into a
new chat, ``workflow`` serves the gallery and download policy, and
``lifecycle`` plus ``quota`` reclaim storage and abandoned reservations.
"""
