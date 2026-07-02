from __future__ import annotations

import pytest

from app.ai.knowledge_base.processor import chunk_text
from app.ai.knowledge_base.retriever import cosine_similarity


class TestChunkText:
    def test_empty_string_returns_empty_list(self):
        assert chunk_text("") == []

    def test_short_text_returns_single_chunk(self):
        text = "Short text that fits in one chunk."
        chunks = chunk_text(text, chunk_size=200, overlap=0)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_is_split_into_multiple_chunks(self):
        text = "word " * 500  # 2500 chars
        chunks = chunk_text(text, chunk_size=500, overlap=0)
        assert len(chunks) == 5

    def test_overlap_means_content_appears_in_consecutive_chunks(self):
        # With chunk_size=60, overlap=20, text of 100 chars:
        # chunk 0: [0:60], chunk 1: [40:100], chunk 2: [80:100]
        text = "A" * 100
        chunks = chunk_text(text, chunk_size=60, overlap=20)
        # Overlap region appears in both chunk 0 and chunk 1
        overlap_region = chunks[0][-20:]
        assert chunks[1].startswith(overlap_region)

    def test_all_content_is_covered_no_content_is_skipped(self):
        text = "ABCDEFGHIJ" * 20  # 200 chars, distinct positions
        chunks = chunk_text(text, chunk_size=80, overlap=20)
        # Every character of the original text must appear in at least one chunk
        combined = "".join(chunks)
        for char in set(text):
            assert char in combined

    def test_chunk_size_respected_except_last_chunk(self):
        text = "x" * 250
        chunks = chunk_text(text, chunk_size=100, overlap=0)
        for chunk in chunks[:-1]:
            assert len(chunk) == 100
        assert len(chunks[-1]) <= 100


class TestCosineSimilarity:
    def test_identical_vectors_return_one(self):
        v = [1.0, 0.5, 0.3]
        assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors_return_zero(self):
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        assert cosine_similarity(v1, v2) == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors_return_negative_one(self):
        v1 = [1.0, 0.0]
        v2 = [-1.0, 0.0]
        assert cosine_similarity(v1, v2) == pytest.approx(-1.0, abs=1e-6)

    def test_empty_vectors_return_zero_without_crash(self):
        assert cosine_similarity([], []) == 0.0

    def test_mismatched_length_vectors_return_zero(self):
        assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0

    def test_zero_vectors_return_zero_without_division_error(self):
        assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0

    def test_similar_vectors_score_higher_than_dissimilar(self):
        base = [1.0, 1.0, 0.0]
        similar = [0.9, 1.0, 0.1]
        dissimilar = [0.0, 0.1, 1.0]
        assert cosine_similarity(base, similar) > cosine_similarity(base, dissimilar)
