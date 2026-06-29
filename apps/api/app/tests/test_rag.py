"""Semantic memory helpers."""

from app.gateways.embedding_gateway import cosine_similarity, parse_embedding, serialize_embedding


def test_cosine_similarity_identical():
    vec = [1.0, 0.0, 0.0]
    assert cosine_similarity(vec, vec) == 1.0


def test_embedding_json_roundtrip():
    vec = [0.1, 0.2, 0.3]
    raw = serialize_embedding(vec)
    parsed = parse_embedding(raw)
    assert parsed == vec
