from app.services.attachment_rag import chunk_text


def test_chunk_text_empty():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_single_chunk():
    assert chunk_text("hello world", chunk_chars=100) == ["hello world"]


def test_chunk_text_overlaps():
    text = "a" * 50 + "b" * 50 + "c" * 50
    chunks = chunk_text(text, chunk_chars=60, overlap=10)
    assert len(chunks) >= 2
    assert all(len(c) <= 60 for c in chunks)
    # Overlap means consecutive chunks share content
    assert chunks[0][-5:] in chunks[1] or chunks[0][-10:][:5] in chunks[1]
